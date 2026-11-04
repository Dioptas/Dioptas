"""Remove operational dataset links without changing retained observations."""
from copy import deepcopy


def repair_removed_record_links(document, records):
    """Reconcile dataset links for an explicitly edited record set.

    Callers gate this migration on eos_records_modified. Older project state
    stores records separately and may have retained links to deleted records.
    Other provenance and cross-record dependencies remain subject to validation.
    """
    live_ids = {record.get('identifier') for record in records}
    linked_ids = {record['identifier'] for record in document.get('eos_records', [])
                  if record.get('identifier')}
    for dataset in document.get('datasets', []):
        linked_ids.update(dataset.get('used_by_eos_records', []))
        linked_ids.update(reduction['eos_record'] for reduction in dataset.get('pressure_reductions', []))
        for view in dataset.get('observation_views', []):
            linked_ids.update(view['eos_records'])
    removed = linked_ids - live_ids
    if not removed:
        return document
    document = remove_record_links(document, removed)
    return document


def remove_record_links(document, identifiers):
    document = deepcopy(document)
    datasets = []
    for dataset in document.get('datasets', []):
        previous_links = dataset.get('used_by_eos_records', [])
        previous_views = dataset.get('observation_views', [])
        if 'used_by_eos_records' in dataset:
            dataset['used_by_eos_records'] = [
                identifier for identifier in previous_links
                if identifier not in identifiers]
        if 'pressure_reductions' in dataset:
            dataset['pressure_reductions'] = [
                reduction for reduction in dataset['pressure_reductions']
                if reduction['eos_record'] not in identifiers]
        if 'observation_views' in dataset:
            views = []
            for view in previous_views:
                links = [identifier for identifier in view['eos_records']
                         if identifier not in identifiers]
                if links:
                    views.append({**view, 'eos_records': links})
            dataset['observation_views'] = views
        # Shared datasets keep their rows, columns and surviving reductions.
        # Previously unlinked source observations also remain intact.
        if (dataset.get('used_by_eos_records') or dataset.get('observation_views')
                or not (previous_links or previous_views)):
            datasets.append(dataset)
    if 'datasets' in document:
        document['datasets'] = datasets
    return document
