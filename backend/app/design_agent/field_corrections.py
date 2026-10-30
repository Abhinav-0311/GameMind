"""The deliberately small, exact-field correction boundary."""
import copy
import json
import re


_INDEX = r'(?:0|[1-9][0-9]*)'
_PATH = re.compile(rf'(?:/quest_hooks/content/quests/{_INDEX}/dialogue_hooks/{_INDEX}'
                   rf'|/npc_archetypes/content/npcs/{_INDEX}/dialogue_triggers/{_INDEX}/situation)\Z')


def validate_target_paths(paths, artifact=None):
    if not isinstance(paths, list) or not 1 <= len(paths) <= 2:
        raise ValueError('Select one or two exact correction fields.')
    if any(not isinstance(path, str) or not _PATH.fullmatch(path) for path in paths):
        raise ValueError('Only individual quest dialogue hooks and NPC situation labels can be corrected.')
    if len(set(paths)) != len(paths):
        raise ValueError('Correction paths must not repeat or overlap.')
    if artifact is not None:
        for path in paths:
            try:
                value = pointer_value(artifact, path)
            except (KeyError, IndexError, TypeError):
                raise ValueError(f'Correction field is unavailable or out of range: {path}') from None
            if not isinstance(value, str):
                raise ValueError(f'Correction field must contain text: {path}')
    return sorted(paths)


def pointer_value(content, path):
    for part in path.split('/')[1:]:
        content = content[int(part)] if isinstance(content, list) else content[part]
    return content


def set_pointer(content, path, value):
    parent_path, key = path.rsplit('/', 1)
    parent = pointer_value(content, parent_path)
    parent[int(key) if isinstance(parent, list) else key] = copy.deepcopy(value)


def correction_effects(path):
    if path.endswith('/situation'):
        return {'path': path.rsplit('/', 1)[0] + '/manual_test',
                'effect': 'Regenerate only this trigger’s manual test from its situation, unchanged speech and eligibility.'}
    return {'path': path.split('/dialogue_hooks/')[0] + '/assumptions',
            'effect': 'Append only the exact server-derived creative-proposal annotation if the corrected hook is not in its cited source; retain all existing assumptions.'}


def expected_correction(before, replacements, evidence):
    from app.design_agent.contracts import DialogueTriggerMapping
    from app.design_agent.grounding import generated_quest_proposal_annotation
    validate_target_paths(list(replacements), before)
    expected = copy.deepcopy(before)
    for path, value in replacements.items():
        if not isinstance(value, str):
            raise ValueError('Correction replacements must be strings.')
        set_pointer(expected, path, value)
    for path in replacements:
        if path.endswith('/situation'):
            trigger = pointer_value(expected, path.rsplit('/', 1)[0])
            trigger['manual_test'] = DialogueTriggerMapping.model_validate(trigger).manual_test
        else:
            quest = pointer_value(expected, path.split('/dialogue_hooks/')[0])
            annotation = generated_quest_proposal_annotation(quest, {str(item['chunk_id']): item for item in evidence})
            if annotation and annotation not in quest['assumptions']:
                quest['assumptions'].append(annotation)
    return expected


def validate_correction_scope(before, candidate, paths, evidence):
    paths = validate_target_paths(paths, before)
    if any(pointer_value(before, path) == pointer_value(candidate, path) for path in paths):
        raise ValueError('Each selected correction field must materially change.')
    expected = expected_correction(before, {path: pointer_value(candidate, path) for path in paths}, evidence)
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    if canonical(candidate) != canonical(expected):
        raise ValueError('The provider changed content outside the selected correction fields and their enumerated dependent effects.')


def correction_context(artifact, paths, evidence):
    result = []
    for path in validate_target_paths(paths, artifact):
        record = pointer_value(artifact, path.split('/dialogue_triggers/')[0] if path.endswith('/situation')
                               else path.split('/dialogue_hooks/')[0])
        if path.endswith('/situation'):
            trigger = pointer_value(artifact, path.rsplit('/', 1)[0])
            context = {key: record[key] for key in ('name', 'archetype', 'dialogue_style') if key in record}
            context.update({key: trigger.get(key) for key in ('text', 'eligibility', 'repeat_policy')})
            type_constraint = 'string, 1–500 characters'
        else:
            context = {key: record[key] for key in ('title', 'objective', 'objectives', 'reward')}
            type_constraint = 'string'
        ids = set(record.get('source_chunk_ids') or artifact[path.split('/')[1]].get('citations', []))
        result.append({'artifact_path': path, 'current_value': pointer_value(artifact, path),
            'type_constraint': type_constraint, 'context': context, 'dependent_effect': correction_effects(path),
            'cited_excerpts': [item for item in evidence if str(item.get('chunk_id')) in ids]})
    return result
