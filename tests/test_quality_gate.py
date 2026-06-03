import pytest
from app.services.quality_gate import QualityGate
from app.services.analysis import Scene

def test_quality_gate():
    gate = QualityGate()
    timeline = [
        {'scene': Scene(start_time=0.0, end_time=2.0, score=9.0, is_hook=True, movement_score=5.0)},
        {'scene': Scene(start_time=2.0, end_time=4.0, score=8.0, is_peak=True, movement_score=4.0)}
    ]

    scores = gate.calculate_scores(timeline)
    assert scores['engagement'] >= 75
    assert scores['retention'] >= 75
    assert scores['visual_quality'] >= 75
    assert gate.is_production_ready(scores) == True

def test_quality_gate_fail():
    gate = QualityGate()
    timeline = [
        {'scene': Scene(start_time=0.0, end_time=10.0, score=1.0, is_hook=False, movement_score=0.1)}
    ]
    scores = gate.calculate_scores(timeline)
    assert gate.is_production_ready(scores) == False
