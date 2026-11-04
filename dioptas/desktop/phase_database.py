# SPDX-License-Identifier: MIT
"""Read-only database inspection and explicit Qt-equivalent structure opt-in."""
from __future__ import annotations

from dioptas.model import eos
from dioptas.model.eos.assumed_structure import (
    assume_tetragonal_perovskite, can_assume_tetragonal_perovskite,
)
from dioptas.model.util.phasesmith import (
    material_has_complete_structure, material_has_diffraction_data,
)


def database_material(material, assume_structure=False):
    if not isinstance(assume_structure, bool):
        raise ValueError('Assumed structure must be a boolean.')
    return assume_tetragonal_perovskite(material) if assume_structure else material


def catalog_payload(query, load_error):
    result = []
    for material in eos.search_materials(query):
        diffraction = material_has_diffraction_data(material)
        can_assume = can_assume_tetragonal_perovskite(material)
        assumed = database_material(material, True) if can_assume else None
        status = ('Crystal structure' if material_has_complete_structure(material)
                  or (material.source.get('kind') == 'cif' and material.source.get('text'))
                  else 'Reference peaks') if diffraction else (
                      'Assumption required' if can_assume else 'EoS only')
        records = []
        for i, record in enumerate(material.eos_records):
            block = record.get('eos') or {}
            thermal = record.get('thermal') or {}
            reference = record.get('reference')
            records.append(dict(
                label=eos.record_label(record), eos=block.get('type', ''),
                thermal=thermal.get('type', ''),
                pressureRange=eos.record_pressure_range(record),
                parameters=block.get('parameters') or {},
                errors=record.get('parameter_errors') or {},
                fixed=record.get('fixed_parameters') or [],
                assessment=eos.record_reproduction(record)[0],
                detail=eos.reference_text(reference) + '\n\n' + eos.record_reproduction(record)[1],
                loadError=load_error(material, i),
                assumedLoadError=load_error(assumed, i) if assumed else '',
                authors=eos.reference_authors(reference), year=eos.reference_year(reference),
                identifier=record.get('identifier', ''),
                citation=eos.reference_text(reference), notes=record.get('notes') or '',
                temperatureRange=record.get('experimental_temperature_range_k'),
                temperatureRef=record.get('temperature_ref'),
                thermalParameters=thermal.get('parameters') or {},
                thermalErrors=thermal.get('parameter_errors') or {},
                thermalFixed=thermal.get('fixed_parameters') or [],
                reportUrl=eos.reconstruction_report_url(record),
                recordUrl=eos.peritheos_record_url(material.identifier, record),
                # Original fields remain available without guessing units or flattening provenance.
                sourceRecord=record,
            ))
        result.append(dict(
            id=material.identifier, name=material.display_name, formula=material.formula,
            spaceGroup=material.space_group, diffraction=diffraction,
            diffractionStatus=status, canAssumeStructure=can_assume,
            assumptionNote=assumed.source['assumed_structure']['note'] if assumed else '',
            defaultReference=material.default_eos_index,
            hold=material.recommendation_hold or '', notes=material.notes,
            references=records,
        ))
    return {'phaseCatalog': result}


def open_documentation(material, reference, kind):
    """Only open a URL owned by the selected bundled record, never a client URL."""
    import webbrowser
    if isinstance(reference, bool) or not isinstance(reference, int) or not 0 <= reference < len(material.eos_records):
        raise ValueError('Select an EoS record.')
    record = material.eos_records[reference]
    if kind == 'report':
        url = eos.reconstruction_report_url(record)
    elif kind == 'record':
        url = eos.peritheos_record_url(material.identifier, record)
    else:
        raise ValueError('Unknown documentation kind.')
    if not url:
        raise ValueError('No documentation is recorded for this selection.')
    if not webbrowser.open(url):
        raise ValueError('The system browser could not open the documentation.')
    return {}
