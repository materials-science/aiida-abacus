__version__ = "0.1.0a0"

import os
from aiida.common.extendeddicts import AttributeDict
from aiida.engine import CalcJob
from aiida import orm
from aiida.common import datastructures, exceptions
from aiida.plugins import DataFactory
from ase.atoms import default

LegacyUpfData = DataFactory("upf")
UpfData = DataFactory("pseudo.upf")


class BaseCalculation(CalcJob):
    """
    A basic calculation.
    """

    _DEFAULT_INPUT_FILE = "INPUT"
    _DEFAULT_OUTPUT_FILE = "aiida.out"
    _PSEUDO_SUBFOLDER = "pseudo"
    _DEFAULT_RETRIEVE_LIST = [
        "OUT.aiida",
        _DEFAULT_INPUT_FILE,
        _DEFAULT_OUTPUT_FILE,
    ]
    _DEFAULT_SETTINGS = {}

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.input(
            "metadata.options.input_filename",
            valid_type=str,
            default=cls._DEFAULT_INPUT_FILE,
        )
        spec.input(
            "metadata.options.output_filename",
            valid_type=str,
            default=cls._DEFAULT_OUTPUT_FILE,
        )
        spec.input(
            "metadata.options.withmpi", valid_type=bool, default=True
        )  # Override default withmpi=False

        spec.input(
            "structure",
            valid_type=orm.StructureData,
            help="The input structure.",
        )
        spec.input(
            "kpoints",
            valid_type=orm.KpointsData,
            help="kpoint mesh or kpoint path",
        )
        spec.input(
            "parameters",
            valid_type=orm.Dict,
            help="The input parameters that are to be used to construct the input file.",
        )
        spec.input_namespace(
            "pseudos",
            valid_type=(LegacyUpfData, UpfData),
            dynamic=True,
            help="A mapping of `UpfData` nodes onto the kind name to which they should apply.",
        )
        spec.input(
            "settings",
            valid_type=orm.Dict,
            required=False,
            default=lambda: orm.Dict(dict=cls._DEFAULT_SETTINGS),
            help="Optional parameters to affect the way the calculation job and the parsing are performed.",
        )
        spec.input(
            "parent_folder",
            valid_type=orm.RemoteData,
            required=False,
            help="An optional working directory of a previously completed calculation to restart from.",
        )

    def prepare_for_submission(self, tempfolder):
        # write INPUT, STRU, KPT, potentials
        local_copy_list = []
        STRU = tempfolder.get_abs_path("STRU")
        KPT = tempfolder.get_abs_path("KPT")
        INPUT = tempfolder.get_abs_path("INPUT")
        local_copy_list_extend = self.write_STRU(STRU)
        self.write_KPT(KPT)
        self.write_INPUT(INPUT)

        local_copy_list.extend(local_copy_list_extend)

        codeinfo = datastructures.CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid
        codeinfo.cmdline_params = []
        codeinfo.stdout_name = self.options.output_filename
        codeinfo.withmpi = self.inputs.metadata.options.withmpi

        calcinfo = datastructures.CalcInfo()
        calcinfo.codes_info = [codeinfo]
        calcinfo.local_copy_list = local_copy_list
        calcinfo.retrieve_list = self._DEFAULT_RETRIEVE_LIST

        return calcinfo

    def write_KPT(self, dst):
        """refer to `aiida-quantumespresso/calculations/__init__.py:_generate_PWCPinputdata`"""

        kpoints = self.inputs.kpoints
        try:
            mesh, offset = kpoints.get_kpoints_mesh()
        except AttributeError as exception:
            raise exceptions.InputValidationError(
                "No mesh found in KpoitnsData."
            )
        kpoints_card_list = [f"K_POINTS\n", "0\n", "Gamma\n"]

        if any([i not in [0, 0.5] for i in offset]):
            raise exceptions.InputValidationError(
                "offset list must only be made of 0 or 0.5 floats"
            )
        the_offset = [0 if i == 0.0 else 1 for i in offset]
        the_6_integers = list(mesh) + the_offset
        kpoints_card_list.append(
            "{:d} {:d} {:d} {:d} {:d} {:d}\n" "".format(*the_6_integers)
        )
        kpoints_card = "".join(kpoints_card_list)
        del kpoints_card_list

        with open(dst, "w", encoding="utf8") as target:
            target.write(kpoints_card)

    def write_STRU(self, dst):
        """refer to `aiida-quantumespresso/calculations/__init__.py:_generate_PWCPinputdata`"""
        from aiida.common.utils import get_unique_filename

        local_copy_list_to_append = []
        settings = self.inputs.settings.get_dict()
        structure = self.inputs.structure
        pseudos = self.inputs.pseudos

        # ------------- ATOMIC_SPECIES ------------
        atomic_species_card_list = []

        # Keep track of the filenames to avoid to overwrite files
        # I use a dictionary where the key is the pseudo PK and the value
        # is the filename I used. In this way, I also use the same filename
        # if more than one kind uses the same pseudo.
        pseudo_filenames = {}

        # I keep track of the order of species
        kind_names = []
        # I add the pseudopotential files to the list of files to be copied
        for kind in structure.kinds:
            # This should not give errors, I already checked before that
            # the list of keys of pseudos and kinds coincides
            pseudo = pseudos[kind.name]

            try:
                # If it is the same pseudopotential file, use the same filename
                filename = pseudo_filenames[pseudo.pk]
            except KeyError:
                # The pseudo was not encountered yet; use a new name and also add it to the local copy list
                filename = get_unique_filename(
                    pseudo.filename, list(pseudo_filenames.values())
                )
                pseudo_filenames[pseudo.pk] = filename
                local_copy_list_to_append.append(
                    (
                        pseudo.uuid,
                        pseudo.filename,
                        os.path.join(self._PSEUDO_SUBFOLDER, filename),
                    )
                )

            kind_names.append(kind.name)
            atomic_species_card_list.append(
                f"{kind.name.ljust(6)} {kind.mass} {filename}\n"
            )

        # I join the lines, but I resort them using the alphabetical order of
        # species, given by the kind_names list. I also store the mapping_species
        # list, with the order of species used in the file
        mapping_species, sorted_atomic_species_card_list = list(
            zip(*sorted(zip(kind_names, atomic_species_card_list)))
        )
        # The format of mapping_species required later is a dictionary, whose
        # values are the indices, so I convert to this format
        # Note the (idx+1) to convert to fortran 1-based lists
        mapping_species = {
            sp_name: (idx + 1) for idx, sp_name in enumerate(mapping_species)
        }
        # I add the first line
        sorted_atomic_species_card_list = ["ATOMIC_SPECIES\n"] + list(
            sorted_atomic_species_card_list
        )
        atomic_species_card = "".join(sorted_atomic_species_card_list)
        # Free memory
        del sorted_atomic_species_card_list
        del atomic_species_card_list

        # ------------ LATTICE_CONSTANT -----------
        # TODO: The lattice constant of the system in unit of Bohr.
        lattice_constant_card = f"LATTICE_CONSTANT\n{1}\n"
        # ------------ LATTICE_VECTORS  -----------
        lattice_vectors_strings = ["LATTICE_VECTORS\n"]
        lattice_vectors_strings.extend(
            ["{0} {1} {2}\n".format(*_) for _ in structure.cell]
        )
        lattice_vectors_card = "".join(lattice_vectors_strings)

        # ------------ ATOMIC_POSITIONS -----------
        # Check on validity of the initial magnetic moment
        initial_magnetic_strings = []
        initial_magnetic = settings.pop("INITIAL_MAGNETIC", None)
        if initial_magnetic is None:
            initial_magnetic_strings = ["0.0"] * len(structure.kinds)
        else:
            if len(initial_magnetic) != len(structure.kinds):
                raise exceptions.InputValidationError(
                    "Input structure contains {:d} elements, but "
                    "initial_magnetic has length {:d}".format(
                        len(structure.kinds), len(initial_magnetic)
                    )
                )
            initial_magnetic_strings = [f"{_:0.1f}" for _ in initial_magnetic]
        # Check on validity of FIXED_COORDS
        fixed_coords_strings = []
        fixed_coords = settings.pop("FIXED_COORDS", None)
        if fixed_coords is None:
            # No fixed_coords specified: a list of 0, The numbers \0 0 0" following the coordinates of the first atom means this atom are not allowed to move in all three directions
            fixed_coords_strings = [
                "  {:d} {:d} {:d}".format(*[0, 0, 0])
            ] * len(structure.sites)
        else:
            if len(fixed_coords) != len(structure.sites):
                raise exceptions.InputValidationError(
                    "Input structure contains {:d} sites, but "
                    "fixed_coords has length {:d}".format(
                        len(structure.sites), len(fixed_coords)
                    )
                )

            for i, this_atom_fix in enumerate(fixed_coords):
                if len(this_atom_fix) != 3:
                    raise exceptions.InputValidationError(
                        f"fixed_coords({i + 1:d}) has not length three"
                    )
                for fixed_c in this_atom_fix:
                    if fixed_c not in [0, 1]:
                        raise exceptions.InputValidationError(
                            f"fixed_coords({i + 1:d}) has non-(0, 1) elements"
                        )

                fixed_coords_strings.append(
                    "  {:d} {:d} {:d}".format(*this_atom_fix)
                )

        abs_pos = [_.position for _ in structure.sites]
        atomic_positions_card_list = ["ATOMIC_POSITIONS\n", "Direct\n"]
        coordinates = abs_pos

        ap_dict = {}
        for site, site_coords, fixed_coords_string in zip(
            structure.sites, coordinates, fixed_coords_strings
        ):
            atom = site.kind_name
            position = "{0:18.10f} {1:18.10f} {2:18.10f} {3}\n".format(
                site_coords[0],
                site_coords[1],
                site_coords[2],
                fixed_coords_string,
            )
            if atom not in ap_dict:
                ap_dict[atom] = {
                    "count": 1,
                    "positions": [position],
                }
            else:
                ap_dict[atom]["count"] += 1
                ap_dict[atom]["positions"].append(position)

        for idx, (k, v) in enumerate(ap_dict.items()):
            atomic_positions_card_list.append(
                "{element}\n{magnetic}\n{natoms}\n{positions}".format(
                    element=k,
                    magnetic=initial_magnetic_strings[idx],
                    natoms=v["count"],
                    positions="".join(v["positions"]),
                )
            )

        atomic_positions_card = "".join(atomic_positions_card_list)
        del atomic_positions_card_list

        with open(dst, "w", encoding="utf8") as target:
            target.write(atomic_species_card)
            target.write(lattice_constant_card)
            target.write(lattice_vectors_card)
            target.write(atomic_positions_card)
        return local_copy_list_to_append

    def validate_parameters(self):
        parameters = AttributeDict(self.inputs.parameters.get_dict())
        parameters.suffix = "aiida"
        parameters.pseudo_dir = f"./{self._PSEUDO_SUBFOLDER}"
        if "ntype" not in parameters:
            parameters.ntype = len(self.inputs.structure.kinds)
        return parameters

    def write_INPUT(self, dst):
        # TODO: validate keys
        input_strings = ["INPUT_PARAMETERS\n"]
        parameters = self.validate_parameters()
        for k, v in sorted(parameters.items()):
            input_strings.append("{0:18}  {1}\n".format(k, v))
        with open(dst, "w", encoding="utf8") as target:
            target.write("".join(input_strings))
