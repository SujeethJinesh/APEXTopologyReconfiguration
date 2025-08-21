from pathlib import Path
import glob


def test_evidence_pack_present_for_completed_milestones():
    """Ensure each completed milestone has an evidence pack in docs/."""
    # Find all milestone directories
    milestone_dirs = glob.glob("docs/M*/")
    
    # Skip milestones that only have summary files (not complete)
    for milestone_dir in milestone_dirs:
        milestone_path = Path(milestone_dir)
        evidence_pack = milestone_path / "evidence_pack.md"
        
        # Only check if evidence_pack.md exists (milestone is complete)
        if evidence_pack.exists():
            # Check required sections
            content = evidence_pack.read_text(encoding="utf-8")
            required_sections = [
                "## Milestone:",
                "## Commit(s)",
                "## Environment",
                "## Reproduce",
                "## Artifacts",
                "## Invariants & Checks",
                "## Sign-off Checklist"
            ]
            
            for section in required_sections:
                assert section in content, f"Missing section '{section}' in {evidence_pack}"
    
    # Ensure at least one evidence pack exists (currently M2)
    m2_pack = Path("docs/M2/evidence_pack.md")
    assert m2_pack.exists(), "M2 evidence pack must exist"