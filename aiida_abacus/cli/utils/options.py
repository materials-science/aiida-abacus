# -*- coding: utf-8 -*-
"""Pre-defined overridable options for commonly used command line interface parameters."""
from aiida import orm
from aiida_abacus.utils import read_structure
from ase.atoms import default
import click

from aiida.cmdline.params import types
from aiida.cmdline.params.options import OverridableOption
from aiida.cmdline.utils import decorators
from aiida.common import exceptions

from . import validate


class StructureParamType(click.ParamType):
    name = "structure"

    def convert(self, value, param, ctx):
        try:
            if isinstance(value, orm.StructureData):
                return value
            else:
                return read_structure(value)
        except Exception:
            self.fail(
                "expected structure node or structure file",
                param,
                ctx,
            )


STRUCTURE = OverridableOption(
    "-S",
    "--structure",
    type=StructureParamType(),
    help="StructureData node or Structure file(xsf,cif,poscar).",
)

KPOINTS_DISTANCE = OverridableOption(
    "-K",
    "--kpoints-distance",
    type=click.FLOAT,
    default=0.5,
    show_default=True,
    help="The minimal distance between k-points in reciprocal space in inverse Ångström.",
)

KPOINTS_MESH = OverridableOption(
    "-k",
    "--kpoints-mesh",
    "kpoints_mesh",
    nargs=3,
    type=click.INT,
    default=None,
    show_default=True,
    callback=validate.validate_kpoints_mesh,
    help="The number of points in the kpoint mesh along each basis vector.",
)

QPOINTS_MESH = OverridableOption(
    "-q",
    "--qpoints-mesh",
    "qpoints_mesh",
    nargs=3,
    type=click.INT,
    show_default=True,
    callback=validate.validate_kpoints_mesh,
    help="The number of points in the qpoint mesh along each basis vector.",
)

MAX_NUM_MACHINES = OverridableOption(
    "-m",
    "--max-num-machines",
    type=click.INT,
    default=1,
    show_default=True,
    help="The maximum number of machines (nodes) to use for the calculations.",
)

MAX_WALLCLOCK_SECONDS = OverridableOption(
    "-w",
    "--max-wallclock-seconds",
    type=click.INT,
    default=1800,
    show_default=True,
    help="the maximum wallclock time in seconds to set for the calculations.",
)

WITH_MPI = OverridableOption(
    "-i",
    "--with-mpi",
    is_flag=True,
    default=True,
    show_default=True,
    help="Run the calculations with MPI enabled.",
)

NUM_MPIPROCS_PER_MACHINE = OverridableOption(
    "-np",
    "--num-mpiprocs-per-machine",
    type=click.INT,
    default=1,
    show_default=True,
    help="The number of process per machine (node) to use for the calculations.",
)
QUEUE_NAME = OverridableOption(
    "--queue",
    default=None,
    show_default=True,
    help="The queue of PBS system.",
)
# PARENT_FOLDER = OverridableOption(
#     "-P",
#     "--parent-folder",
#     "parent_folder",
#     type=types.DataParamType(sub_classes=("aiida.data:remote",)),
#     show_default=True,
#     required=False,
#     help="The PK of a parent remote folder (for restarts).",
# )

DAEMON = OverridableOption(
    "-d",
    "--daemon",
    is_flag=True,
    default=False,
    show_default=True,
    help="Submit the process to the daemon instead of running it locally.",
)

# AUTOMATIC_PARALLELIZATION = OverridableOption(
#     "-a",
#     "--automatic-parallelization",
#     is_flag=True,
#     default=False,
#     show_default=True,
#     help="Enable the automatic parallelization option of the workchain.",
# )

CLEAN_WORKDIR = OverridableOption(
    "-x",
    "--clean-workdir",
    is_flag=True,
    default=False,
    show_default=True,
    help="Clean the remote folder of all the launched calculations after completion of the workchain.",
)

# ECUTWFC = OverridableOption(
#     "-W",
#     "--ecutwfc",
#     type=click.FLOAT,
#     help="The plane wave cutoff energy in Ry.",
# )

# ECUTRHO = OverridableOption(
#     "-R",
#     "--ecutrho",
#     type=click.FLOAT,
#     help="The charge density cutoff energy in Ry.",
# )

# HUBBARD_U = OverridableOption(
#     "-U",
#     "--hubbard-u",
#     nargs=2,
#     multiple=True,
#     type=click.Tuple([str, float]),
#     help="Add a Hubbard U term to a specific kind.",
#     metavar="<KIND MAGNITUDE>...",
# )

# HUBBARD_V = OverridableOption(
#     "-V",
#     "--hubbard-v",
#     nargs=4,
#     multiple=True,
#     type=click.Tuple([int, int, int, float]),
#     help="Add a Hubbard V interaction between two sites.",
#     metavar="<SITE SITE TYPE MAGNITUDE>...",
# )

# HUBBARD_FILE = OverridableOption(
#     "-H",
#     "--hubbard-file",
#     "hubbard_file_pk",
#     type=types.DataParamType(sub_classes=("aiida.data:singlefile",)),
#     help="SinglefileData containing Hubbard parameters from a HpCalculation to use as input for Hubbard V.",
# )

# STARTING_MAGNETIZATION = OverridableOption(
#     "--starting-magnetization",
#     nargs=2,
#     multiple=True,
#     type=click.Tuple([str, float]),
#     help="Add a starting magnetization to a specific kind.",
#     metavar="<KIND MAGNITUDE>...",
# )

# SMEARING = OverridableOption(
#     "--smearing",
#     nargs=2,
#     default=(None, None),
#     type=click.Tuple([str, float]),
#     help="Add smeared occupations by specifying the type and amount of smearing.",
#     metavar="<TYPE DEGAUSS>",
# )


PARAMETERS = OverridableOption(
    "--parameters",
    "-p",
    nargs=2,
    multiple=True,
    type=click.Tuple([str, float]),
    help="Override parameters in Data AbacusParameters by specifying the key and value of parameter. e.g. <ecutwfc 80>...",
    metavar="<key value>...",
)
PARAMETERS_NAME = OverridableOption(
    "--parameters-name",
    help="Type `verdi data abacus list` to see available parameters.",
    default="default",
    show_default=True,
)
PSEUDO_FAMILY = OverridableOption("--pseudo-family", help="pseudo family name")
CUTOFFS = OverridableOption(
    "--cutoffs",
    type=float,
    nargs=2,
    default=None,
    help="should be [ecutwfc] [dual]. [ecutrho] will get by dual * ecutwfc",
)
SYSTEM_2D = OverridableOption(
    "--system-2d",
    is_flag=True,
    help="Set mesh to [x, x, 1]",
)
RUN_RELAX = OverridableOption(
    "--run-relax",
    is_flag=True,
    help="Whether to run relax before scf.",
)
