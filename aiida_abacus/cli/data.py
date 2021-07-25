# -*- coding: utf-8 -*-
"""
Command line interface (cli) for aiida_abacus.

Register new commands either via the "console_scripts" entry point or plug them
directly into the 'verdi' command by using AiiDA-specific entry points like
"aiida.cmdline.data" (both in the setup.json file).
"""

import sys
import click
import json
from aiida.cmdline.utils import decorators
from aiida.cmdline.commands.cmd_data import verdi_data
from aiida.cmdline.params.types import DataParamType
from aiida.orm import QueryBuilder
from aiida.plugins import DataFactory
from sqlalchemy.sql.functions import user


# See aiida.cmdline.data entry point in setup.json
@verdi_data.group("abacus")
def data_cli():
    """Command line interface for aiida-abacus"""


@data_cli.command("list")
@decorators.with_dbenv()
def list_():  # pylint: disable=redefined-builtin
    """
    Display all AbacusParameters nodes
    """
    AbacusParameters = DataFactory("abacus")

    qb = QueryBuilder()
    qb.append(AbacusParameters)
    results = qb.all()

    s = ""
    for result in results:
        obj = result[0]
        s += "pk: {}, name: {}, username: {}, ctime: {}\n".format(
            obj.pk, obj.get_extra("name"), obj.get_extra("username"), obj.ctime
        )
    sys.stdout.write(s)


@data_cli.command("show")
@click.argument("IDENTIFIER", metavar="IDENTIFIER", type=click.STRING)
@decorators.with_dbenv()
def show(identifier):  # pylint: disable=redefined-builtin
    """
    Display details of a AbacusParameters node with name or id
    """
    AbacusParameters = DataFactory("abacus")
    try:
        identifier = int(identifier)
    except Exception as err:
        pass

    qb = QueryBuilder()
    qb.append(
        AbacusParameters,
        filters={"or": [{"id": identifier}, {"extras.name": identifier}]},
    )
    results = qb.all()

    s = ""
    for result in results:
        obj = result[0]
        s += "Info\n---\npk: {}, name: {}, username: {}, ctime: {}\n--\nParameters\n---\n{}\n---\n".format(
            obj.pk,
            obj.get_extra("name"),
            obj.get_extra("username"),
            obj.ctime,
            json.dumps(obj.attributes, sort_keys=True, indent=2),
        )
    sys.stdout.write(s)


@data_cli.command("add")
@click.argument("json_file", type=click.Path(dir_okay=False))
@click.argument("name", metavar="IDENTIFIER", type=click.STRING)
@click.argument("username", type=click.STRING)
@decorators.with_dbenv()
def add(json_file, name, username):  # pylint: disable=redefined-builtin
    """
    Add new parameters from a json file.
    """
    with open(json_file, "r") as f:
        params = json.loads(f.read())
    AbacusParameters = DataFactory("abacus")
    new_params = AbacusParameters(name=name, username=username, dict=params)
    new_params.store()


@data_cli.command("export")
@click.argument("node", metavar="IDENTIFIER", type=DataParamType())
@click.option(
    "--outfile",
    "-o",
    type=click.Path(dir_okay=False),
    help="Write output to file (default: print to stdout).",
)
@decorators.with_dbenv()
def export(node, outfile):
    """Export a AbacusParameters node (identified by PK, UUID or label) to json."""
    string = json.dumps(node.attributes, sort_keys=True, indent=2)

    if outfile:
        with open(outfile, "w") as f:
            f.write(string)
    else:
        click.echo(string)


@data_cli.command("del")
@click.argument("node", metavar="IDENTIFIER", type=DataParamType())
@decorators.with_dbenv()
def export(node):
    """Export a AbacusParameters node (identified by PK, UUID or label) to json."""
    node.objects.delete(node.id)
