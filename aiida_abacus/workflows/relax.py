from aiida.common import exceptions
from aiida.common.exceptions import InputValidationError
from aiida.plugins.factories import CalculationFactory
from aiida_abacus.data.parameters import AbacusParameters
from aiida.engine import WorkChain, ToContext, if_, while_, append_
from aiida.common import AttributeDict
from aiida import orm
from aiida.orm.querybuilder import QueryBuilder
from aiida.orm.nodes.data.upf import get_pseudos_from_structure
from aiida_abacus.calculations.functions import (
    create_kpoints_from_distance,
)

BaseCalculation = CalculationFactory("abacus.base")


def validate_inputs(inputs, _):
    if "pseudo_family" not in inputs and "pseudos" not in inputs["base"]:
        raise InputValidationError(
            "You have to specifiy pseudo_family or pseudos."
        )
    if "pseudo_family" in inputs and "pseudos" in inputs["base"]:
        raise InputValidationError(
            "You can only specifiy pseudo_family or pseudos."
        )


class RealxWorkChain(WorkChain):
    """RealxWorkChain AI is creating summary for RealxWorkChain"""

    _DEFAULT_RELAX_SCHEMES = ["relax", "cell-relax"]

    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        super().define(spec)
        spec.expose_inputs(
            BaseCalculation,
            namespace="base",
            exclude=(
                "clean_workdir",
                "structure",
                "parent_folder",
                "kpoints",
                "parameters",
            ),
            namespace_options={
                "help": "Inputs for the `BaseWorkChain` for the main relax loop."
            },
        )
        spec.input(
            "structure",
            valid_type=orm.StructureData,
            help="The input structure.",
        )
        spec.input(
            "parameters_name",
            valid_type=orm.Str,
            required=False,
            help="The name of Data AbacusParameters. Use `verdi data abacus list` to show available parameters.",
        )
        spec.input(
            "parameters",
            valid_type=orm.Dict,
            required=False,
            help="Override parameters in AbacusPatameters.",
        )
        spec.input(
            "pseudo_family",
            valid_type=orm.Str,
            required=False,
            help="An alternative to specifying the pseudo potentials manually in `pseudos`: one can specify the name of an existing pseudo potential family and the work chain will generate the pseudos automatically based on the input structure.",
        )
        spec.input(
            "max_meta_convergence_iterations",
            valid_type=orm.Int,
            default=lambda: orm.Int(1),
            help="The maximum number of variable cell relax iterations in the meta convergence cycle.",
        )
        spec.input(
            "system_2d",
            valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help="Set the mesh to [x, x, 1]",
        )
        spec.input(
            "clean_workdir",
            valid_type=orm.Bool,
            default=lambda: orm.Bool(False),
            help="If `True`, work directories of all called calculation will be cleaned at the end of execution.",
        )
        spec.inputs.validator = validate_inputs
        spec.outline(
            cls.setup,
            while_(cls.should_run_relax)(
                cls.run_relax,
                cls.inspect_relax,
            ),
            # if_(cls.should_run_final_scf)(
            #     cls.run_final_scf,
            #     cls.inspect_final_scf,
            # ),
            cls.results,
        )
        spec.exit_code(
            401,
            "ERROR_SUB_PROCESS_FAILED_RELAX",
            message="the relax BaseCalculation sub process failed",
        )
        spec.exit_code(
            402,
            "ERROR_SUB_PROCESS_FAILED_FINAL_SCF",
            message="the final scf BaseCalculation sub process failed",
        )
        spec.output(
            "output_structure",
            valid_type=orm.StructureData,
            required=False,
            help="The successfully relaxed structure.",
        )

    def get_abacus_paratamters(self):
        name = self.inputs.parameters_name.value
        qb = QueryBuilder()
        query_obj = qb.append(AbacusParameters, filters={"extras.name": name})
        count = query_obj.count()
        if count != 1:
            raise ValueError(
                "Invalid name {} of AbacusParameters Data. Matched {}.".format(
                    name, count
                )
            )
        self.ctx.parameters = query_obj.first()[0].attributes
        self.ctx.parameters.update(self.inputs.parameters.get_dict())
        self.ctx.parameters = AttributeDict(self.ctx.parameters)

        # TODO: generate recommended cutoffs from pseudos
        if "ecutwfc" not in self.ctx.parameters:
            raise ValueError(
                "You need to spercify `ecutwfc` in current version."
            )

        # TODO: Only supports `pw` Currently. Others: `lcao`, `lcao_in_pw`
        basis_type = self.ctx.parameters.get("basis_type", "pw")

        if basis_type != "pw":
            raise ValueError("Only supports basis_type `pw` Currently.")

        # TODO: nbnd
        nbands_factor = self.ctx.parameters.pop("nbands_factor", None)
        if nbands_factor is not None:
            pass

    def generate_kpoints_mesh(self):
        kpoints_mesh_density = self.ctx.parameters.pop(
            "kpoints_mesh_density", "0.2"
        )
        # TODO: supports offset
        kpoints_mesh_offset = self.ctx.parameters.pop(
            "kpoints_mesh_offset", None
        )
        kpoints = create_kpoints_from_distance(
            **{
                "structure": self.ctx.current_structure,
                "distance": orm.Float(kpoints_mesh_density),
                "force_parity": orm.Bool(False),
                "system_2d": self.inputs.system_2d,
                "metadata": {"call_link_label": "create_kpoints_from_distance"},
            }
        )
        self.ctx.kpoints = kpoints

    def setup(self):
        self.ctx.current_number_of_bands = None
        self.ctx.current_structure = self.inputs.structure
        self.ctx.current_cell_volume = None
        self.ctx.is_converged = False
        self.ctx.iteration = 0
        self.get_abacus_paratamters()
        self.generate_kpoints_mesh()
        self.prepare_for_relax()

    def should_run_relax(self):
        return (
            not self.ctx.is_converged
            and self.ctx.iteration
            < self.inputs.max_meta_convergence_iterations.value
        )

    def prepare_for_relax(self):
        calculation = self.ctx.parameters.get("calculation", "relax")
        if calculation not in self._DEFAULT_RELAX_SCHEMES:
            calculation = "relax"
        self.ctx.relax_inputs = AttributeDict(
            self.exposed_inputs(BaseCalculation, namespace="base")
        )

        self.ctx.relax_inputs.kpoints = self.ctx.kpoints

        if "pseudo_family" in self.inputs:
            self.ctx.relax_inputs.pseudos = get_pseudos_from_structure(
                self.ctx.current_structure, self.inputs.pseudo_family.value
            )

        self.ctx.relax_inputs.parameters = self.ctx.parameters
        self.ctx.relax_inputs.parameters.calculation = calculation
        self.ctx.relax_inputs.structure = self.ctx.current_structure

    def run_relax(self):
        self.ctx.iteration += 1
        inputs = self.ctx.relax_inputs
        inputs.structure = self.ctx.current_structure
        if self.ctx.current_number_of_bands is not None:
            inputs.parameters["nbnd"] = self.ctx.current_number_of_bands

        # Set the `CALL` link label
        inputs.metadata.call_link_label = f"iteration_{self.ctx.iteration:02d}"

        inputs.parameters = orm.Dict(dict=inputs.parameters)

        running = self.submit(BaseCalculation, **inputs)

        self.report(f"launching BaseCalculation<{running.pk}>")

        return ToContext(workchains=append_(running))

    def inspect_relax(self):
        """Inspect the results of the last `BaseCalculation`.

        Compare the cell volume of the relaxed structure of the last completed workchain with the previous. If the
        difference ratio is less than the volume convergence threshold we consider the cell relaxation converged.
        """
        workchain = self.ctx.workchains[-1]

        if workchain.is_excepted or workchain.is_killed:
            self.report("relax BaseCalculation was excepted or killed")
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_RELAX

        if workchain.is_failed:
            self.report(
                f"relax BaseCalculation failed with exit status {workchain.exit_status}"
            )
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_RELAX

        # try:
        #     structure = workchain.outputs.output_structure
        # except exceptions.NotExistent:
        #     self.report(
        #         "`cell-relax` or `relax` BaseCalculation finished successfully but without output structure"
        #     )
        #     return self.exit_codes.ERROR_SUB_PROCESS_FAILED_RELAX

        # Set relaxed structure as input structure for next iteration
        # self.ctx.current_structure = structure
        # self.ctx.current_number_of_bands = (
        #     workchain.outputs.output_parameters.get_dict()["number_of_bands"]
        # )

    def results(self):
        self.report(
            f"workchain completed after {self.ctx.iteration} iterations"
        )

    def on_terminated(self):
        """Clean the working directories of all child calculations if `clean_workdir=True` in the inputs."""
        super().on_terminated()

        if self.inputs.clean_workdir.value is False:
            self.report("remote folders will not be cleaned")
            return

        cleaned_calcs = []

        for called_descendant in self.node.called_descendants:
            if isinstance(called_descendant, orm.CalcJobNode):
                try:
                    called_descendant.outputs.remote_folder._clean()  # pylint: disable=protected-access
                    cleaned_calcs.append(called_descendant.pk)
                except (IOError, OSError, KeyError):
                    pass

        if cleaned_calcs:
            self.report(
                f"cleaned remote folders of calculations: {' '.join(map(str, cleaned_calcs))}"
            )
