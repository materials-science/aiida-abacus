from aiida import orm
from ase.io import read as aseread


def read_structure(structure_file, store=False):
    structure = orm.StructureData(ase=aseread(structure_file))
    if store is True:
        structure.store()
    print(
        "Structure {} read and stored with pk {}.".format(
            structure.get_formula(), structure.pk
        )
    )
    return structure
