import copy

import pytest

from ai import AI
from schemas import normalize_calculation_prompt, validate_calculation_prompt, validate_quiz
from test_app import FakeAI, NOTES, complete, generate, prepared_notes, setup


@pytest.mark.parametrize('prompt', [
    'For the linear regression loss in the source, what is the condition number ' + r'\(\kappa\)?',
    'Compute the update with w=3, eta=0.1, and gradient=6.',
    r'What is \[\kappa\]?',
    r'Given \[\kappa = ?\], calculate it.',
    r'\[w=3,\quad\eta=0.1,\quad g=6\] Calculate the update from the source.',
    r'\[w^{\mathrm{new}}=w-\eta g\] Calculate the new value.',
])
def test_incomplete_or_inline_only_problem_is_rejected(prompt):
    source = {'id': 's', 'text': NOTES, 'name': 'Notes', 'locator': 'Notes', 'kind': 'text'}
    raw = FakeAI().generate({'format': 'calculation', 'count': 1}, [source])
    raw['questions'][0]['prompt'] = prompt
    raw['questions'][0]['problemEquation'] = None
    with pytest.raises(ValueError, match='standalone LaTeX'):
        validate_quiz(raw, [source], 'calculation', 1)


@pytest.mark.parametrize('prompt', [
    r'\[L(w)=w^2,\quad w=3\] Evaluate \(L(w)\).',
    r'\[w^{\mathrm{new}}=w-\eta g\]\[w=3,\quad\eta=0.1,\quad g=6\] Find the updated value.',
    r'\[H=\begin{bmatrix}2&0\\0&20\end{bmatrix}\] Compute the spectral condition number.',
    r'$$N=4096,\quad B=128,\quad s=\frac{N}{B}$$ Compute the number of steps.',
    r'\\[f(x)=\frac{x^2}{2},\quad x=3\\] Evaluate the function.',
    r'\[n^2hLB\] Given n=5, h=4, L=3, B=2, evaluate the count.',
    r'\[\frac{N}{B}\] Given N=4096 and B=128, evaluate the step count.',
])
def test_complete_display_equations_are_accepted(prompt):
    validate_calculation_prompt(prompt)


def test_generation_allows_new_examples_grounded_in_lecture_concepts(monkeypatch):
    captured = {}
    def structured(system, content, schema):
        captured['system'] = system
        return {}
    ai = AI()
    monkeypatch.setattr(ai, 'structured', structured)
    ai.generate({'prompt': 'Condition numbers', 'format': 'calculation', 'count': 4,
                 'difficulty': 'intermediate'}, [])
    assert 'solvable from the visible prompt alone' in captured['system']
    assert 'You MAY choose' in captured['system']
    assert 'The source does NOT need to contain a worked example or numerical givens' in captured['system']
    assert 'new practice example' in captured['system']
    assert 'formatting example only' in captured['system']
    assert 'Do not reveal the computed answer in the prompt' in captured['system']


@pytest.mark.parametrize('prompt', [
    r'For \(f(x)=2x+1\), find \(f(3)\).',
    r'For $f(x)=2x+1$, find $f(3)$.',
    r'\[f(x)=ax\] Given a=2 and x=3, evaluate the function.',
])
def test_equation_display_normalization_preserves_the_problem(prompt):
    normalized = normalize_calculation_prompt(prompt)
    validate_calculation_prompt(normalized)
    assert r'\[' in normalized
    assert normalize_calculation_prompt(normalized) == normalized


def test_new_equations_can_cite_concept_only_material():
    source = {'id': 's', 'name': 'Concept lecture', 'kind': 'text', 'locator': 'Notes',
              'text': 'Gradient descent updates a parameter by subtracting the learning rate times its gradient.'}
    raw = FakeAI().generate({'format': 'calculation', 'count': 1}, [source])
    raw['questions'][0]['prompt'] = (r'Practice example: \(w^{\mathrm{new}}=w-\eta g\). '
                                    r'Given \(w=3,\quad\eta=0.1,\quad g=6\), find the updated parameter.')
    quiz = validate_quiz(raw, [source], 'calculation', 1)
    q = quiz['questions'][0]
    assert q['practiceExample'] is True
    assert q['source']['quote'] == source['text']
    assert q['numericAnswer'] == 2.4
    assert r'\[w^{\mathrm{new}}' in q['prompt']
    from study_groups import snapshot
    shared = snapshot({**quiz, 'format': 'calculation'})
    assert shared['questions'][0]['practiceExample'] is True
    assert shared['questions'][0]['source']['quote'] == source['text']


def test_required_equation_field_is_rendered_without_repeating_it():
    source = {'id': 's', 'name': 'Concept lecture', 'kind': 'text', 'locator': 'Notes', 'text': NOTES}
    raw = FakeAI().generate({'format': 'calculation', 'count': 1}, [source])
    q = raw['questions'][0]
    q['prompt'] = 'Given w=3, eta=0.1 and g=6, calculate the updated parameter.'
    validated = validate_quiz(raw, [source], 'calculation', 1)['questions'][0]
    assert validated['prompt'].startswith(r'\[w^{\mathrm{new}} = w - \eta g\]')
    raw = FakeAI().generate({'format': 'calculation', 'count': 1}, [source])
    raw['questions'][0]['problemEquation'] = r'w^{\mathrm{new}}=w-\eta g'
    validated = validate_quiz(raw, [source], 'calculation', 1)['questions'][0]
    assert validated['prompt'].count('w^{\\mathrm{new}}') == 1
    from schemas import generation_schema
    schema = generation_schema('calculation').model_json_schema()['$defs']['Question_calculation']
    assert 'problemEquation' in schema['required']
    assert schema['properties']['problemEquation']['type'] == 'string'


def test_selector_accepts_concept_only_sources_for_practice(monkeypatch):
    captured = {}
    def structured(system, content, schema):
        captured['system'] = system
        return {'status': 'ready', 'message': '', 'sourceIds': ['s']}
    ai = AI()
    monkeypatch.setattr(ai, 'structured', structured)
    result = ai.select('Create calculation practice', [
        {'id': 's', 'locator': 'Page 1', 'text': 'Gradient descent follows the negative gradient.'}])
    assert result['status'] == 'ready'
    assert 'even if they contain no worked example' in captured['system']


def test_displayed_answer_mismatch_is_still_rejected():
    source = {'id': 's', 'name': 'Notes', 'kind': 'text', 'locator': 'Notes', 'text': NOTES}
    raw = FakeAI().generate({'format': 'calculation', 'count': 1}, [source])
    raw['questions'][0]['answer'] = '3.6'
    with pytest.raises(ValueError, match='Question 1: displayed answer'):
        validate_quiz(raw, [source], 'calculation', 1)


def test_worker_repairs_a_missing_equation_without_replacing_saved_work(setup, monkeypatch):
    client, store, engine, ai = setup
    material_id = prepared_notes(client, engine)
    earlier = generate(client, engine, material_id)
    original_generate = ai.generate
    feedback_received = []
    def generate_bad_then_repair(params, sources, validation_feedback=''):
        feedback_received.append(validation_feedback)
        raw = original_generate(params, sources, validation_feedback)
        if not validation_feedback:
            for question in raw['questions']:
                question['prompt'] = 'Calculate the condition number of the loss in the source.'
                question['problemEquation'] = None
        return raw
    monkeypatch.setattr(ai, 'generate', generate_bad_then_repair)
    new_quiz = generate(client, engine, material_id, 'calculation')
    assert len(feedback_received) == 2
    assert 'standalone LaTeX' in feedback_received[1]
    import json
    assert 'previousAttempt' in json.loads(feedback_received[1])
    assert all(r'\[' in q['prompt'] for q in new_quiz['questions'])
    assert client.get('/api/quizzes/' + earlier['id']).json()['questions'] == earlier['questions']


def test_invalid_problem_after_retry_is_not_saved(setup, monkeypatch):
    client, store, engine, ai = setup
    material_id = prepared_notes(client, engine)
    earlier = generate(client, engine, material_id)
    original_generate = ai.generate
    def invalid(params, sources, validation_feedback=''):
        raw = copy.deepcopy(original_generate(params, sources, validation_feedback))
        for q in raw['questions']:
            q['prompt'] = 'Compute the loss mentioned in the source.'
            q['problemEquation'] = None
        return raw
    monkeypatch.setattr(ai, 'generate', invalid)
    response = client.post('/api/quizzes', json={'materialId': material_id,
        'prompt': 'Numerical practice', 'format': 'calculation', 'count': 4, 'difficulty': 'beginner'})
    engine.run(response.json()['jobId'])
    job = client.get('/api/jobs/' + response.json()['jobId']).json()
    assert job['status'] == 'failed'
    assert 'standalone LaTeX' in job['error']
    assert client.get('/api/quizzes/' + earlier['id']).json()['questions'] == earlier['questions']
