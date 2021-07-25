from . import cmd_launch
from aiida import orm
from aiida.cmdline.utils import decorators
from aiida.cmdline.params import options as options_core
from aiida.plugins import WorkflowFactory
from .utils import options
from .utils import launch


@cmd_launch.command("relax")
@options.STRUCTURE()
@options.PARAMETERS_NAME()
@options.PARAMETERS()
@options.PSEUDO_FAMILY()
@options.SYSTEM_2D()
@options_core.CODE()
@options.MAX_NUM_MACHINES()
@options.NUM_MPIPROCS_PER_MACHINE()
@options.DAEMON()
@options.CLEAN_WORKDIR()
@decorators.with_dbenv()
def launch_relax(
    structure,
    parameters_name,
    parameters,
    pseudo_family,
    system_2d,
    code,
    max_num_machines,
    num_mpiprocs_per_machine,
    daemon,
    clean_workdir,
):
    parameters_dict = {}
    for t in parameters:
        parameters_dict[t[0]] = t[1]

    launch.launch_process(
        WorkflowFactory("abacus.relax"),
        daemon,
        **{
            "structure": structure,
            "parameters_name": orm.Str(parameters_name),
            "parameters": orm.Dict(dict=parameters_dict),
            "pseudo_family": orm.Str(pseudo_family),
            "system_2d": orm.Bool(system_2d),
            "clean_workdir": orm.Bool(clean_workdir),
            "base": {
                "code": code,
                "metadata": {
                    "options": {
                        "resources": {
                            "num_machines": int(max_num_machines),
                            "num_mpiprocs_per_machine": int(
                                num_mpiprocs_per_machine
                            ),
                        },
                        "withmpi": True,
                    },
                },
            },
            "metadata": {
                "description": "Relax job submission with the aiida_abacus plugin",
            },
        }
    )
