"""Unit tests for the Jaccard scorer. No DB, no fixtures needed."""
import pytest

from features.teams.matching import jaccard, normalize_tags, score_team


class TestNormalizeTags:
    def test_lowercases(self):
        assert normalize_tags(["React"]) == ["react"]

    def test_trims(self):
        assert normalize_tags(["  react  "]) == ["react"]

    def test_case_and_whitespace_insensitive(self):
        assert normalize_tags(["React ", " REACT"]) == ["react"]

    def test_drops_empties(self):
        assert normalize_tags(["react", "", "   "]) == ["react"]

    def test_dedupes(self):
        assert normalize_tags(["react", "React", "python"]) == ["react", "python"]

    def test_none_input(self):
        assert normalize_tags(None) == []


class TestJaccard:
    def test_identical_sets_is_one(self):
        assert jaccard(["react", "python"], ["react", "python"]) == 1.0

    def test_disjoint_is_zero(self):
        assert jaccard(["react"], ["rust"]) == 0.0

    def test_both_empty_is_zero_not_zero_division(self):
        assert jaccard([], []) == 0.0

    def test_one_side_empty_is_zero(self):
        assert jaccard(["react"], []) == 0.0
        assert jaccard([], ["react"]) == 0.0

    def test_half_overlap(self):
        # |A n B| = 1, |A u B| = 3 -> 1/3
        assert jaccard(["react"], ["react", "python", "ml"]) == pytest.approx(1 / 3)

    def test_order_independent(self):
        assert jaccard(["a", "b", "c"], ["c", "b", "a"]) == 1.0

    def test_normalizes_before_comparing(self):
        assert jaccard(["React "], ["react"]) == 1.0

    def test_none_safe(self):
        assert jaccard(None, None) == 0.0


class TestScoreTeam:
    def test_perfect_completion_with_branch_bonus_clamps_to_100(self):
        result = score_team(["react"], ["react"], same_branch=True)
        assert result["fill_pct"] == 100.0
        assert result["branch_bonus"] == 15.0
        assert result["score"] == 100.0

    def test_no_branch_bonus_by_default(self):
        assert score_team(["react"], ["react"])["branch_bonus"] == 0.0

    def test_branch_adds_exactly_fifteen(self):
        # A partial score, so the bonus is not swallowed by the 100 clamp.
        without = score_team(["nodejs"], ["react", "python"], wanted=["nodejs"])
        with_branch = score_team(["nodejs"], ["react", "python"], wanted=["nodejs"], same_branch=True)
        assert without["score"] < 100.0
        assert with_branch["score"] - without["score"] == pytest.approx(15.0)

    def test_matching_and_missing_are_disjoint(self):
        result = score_team(["react", "python"], ["react", "ml"])
        assert result["matching_skills"] == ["react"]
        assert result["missing_skills"] == ["ml"]
        assert not set(result["matching_skills"]) & set(result["missing_skills"])

    def test_empty_user_skills_gives_zero(self):
        result = score_team([], ["react"])
        assert result["score"] == 0.0
        assert result["missing_skills"] == ["react"]

    def test_score_never_exceeds_100(self):
        result = score_team(["react", "python", "ml"], ["react", "python", "ml"], same_branch=True)
        assert result["score"] <= 100.0

    def test_returns_all_expected_keys(self):
        result = score_team(["react"], ["react"])
        for key in (
            "score",
            "fill_pct",
            "overlap_pct",
            "coverage_pct",
            "branch_bonus",
            "team_gap",
            "matching_skills",
            "missing_skills",
            "fills_gaps",
            "same_branch",
            "reason",
        ):
            assert key in result


class TestGapFilling:
    """
    The distinction that makes this a team-finder rather than a similarity
    search. A team recruiting a *new* member wants someone who adds what the
    current members lack.
    """

    def test_gap_is_stack_plus_wanted_minus_member_skills(self):
        result = score_team(
            ["gcp"],
            ["react", "python"],
            wanted=["gcp", "terraform"],
            member_skills=["react"],
        )
        # team needs react, python, gcp, terraform; react is already covered
        assert result["team_gap"] == ["gcp", "python", "terraform"]

    def test_candidate_fills_the_gap(self):
        result = score_team(
            ["python"], ["react", "python"], member_skills=["react"]
        )
        assert result["fills_gaps"] == ["python"]
        assert result["fill_pct"] == 100.0

    def test_duplicating_an_existing_member_skill_scores_nothing(self):
        """The owner already brings react, so another react dev closes no gap."""
        result = score_team(["react"], ["react", "python"], member_skills=["react"])
        assert result["fills_gaps"] == []
        assert result["fill_pct"] == 0.0
        assert "so does everyone already there" in result["reason"]

    def test_complementary_person_outranks_a_duplicate(self):
        """
        The behaviour the whole score exists for.

        The team already has react + python covered by its owner and wants
        nodejs and gcp. Candidate A knows react and python - a perfect
        similarity match. Candidate B knows nodejs - shares nothing with the
        team, yet B is the person it is actually recruiting.
        """
        stack = ["react", "python"]
        already = ["react", "python"]

        duplicate = score_team(["react", "python"], stack, wanted=["nodejs", "gcp"], member_skills=already)
        complement = score_team(["nodejs"], stack, wanted=["nodejs", "gcp"], member_skills=already)

        assert duplicate["overlap_pct"] == 100.0
        assert duplicate["fills_gaps"] == []
        assert duplicate["fill_pct"] == 0.0

        assert complement["overlap_pct"] == 0.0
        assert complement["fills_gaps"] == ["nodejs"]
        assert complement["fill_pct"] == 50.0

        assert complement["score"] > duplicate["score"]

    def test_covering_the_whole_gap_outranks_a_partial_filler(self):
        """
        Closing the entire gap beats closing half of it, even though this
        candidate shares no skill with the team's existing stack.
        """
        stack = ["react", "python"]
        already = ["react", "python"]
        wanted = ["nodejs", "gcp", "docker"]

        full = score_team(["nodejs", "gcp", "docker"], stack, wanted=wanted, member_skills=already)
        partial = score_team(["nodejs"], stack, wanted=wanted, member_skills=already)
        duplicate = score_team(["react", "python"], stack, wanted=wanted, member_skills=already)

        assert full["fill_pct"] == 100.0
        assert partial["fill_pct"] == pytest.approx(33.3, abs=0.1)
        assert full["score"] > partial["score"] > duplicate["score"]

    def test_familiarity_breaks_a_tie_on_fill(self):
        """Equal gap contribution, different familiarity with their stack."""
        stack = ["react", "python"]
        already = ["react", "python"]   # stack fully covered, only nodejs wanted
        wanted = ["nodejs"]

        familiar = score_team(["nodejs", "react"], stack, wanted=wanted, member_skills=already)
        new = score_team(["nodejs", "rust"], stack, wanted=wanted, member_skills=already)

        assert familiar["fill_pct"] == new["fill_pct"] == 100.0
        assert familiar["overlap_pct"] > new["overlap_pct"]
        assert familiar["score"] > new["score"]

    def test_no_wish_list_is_not_penalised(self):
        """A team that never published `wanted` must still be able to score 100."""
        result = score_team(["react"], ["react"])
        assert result["score"] == 100.0

    def test_wanted_list_counts_toward_the_gap(self):
        result = score_team(["gcp"], ["react"], wanted=["gcp"])
        assert result["fills_gaps"] == ["gcp"]
        assert result["coverage_pct"] == 100.0

    def test_fully_covered_team_offers_nobody_a_match(self):
        """
        The regression that made every stranger look like a top candidate for a
        fully-staffed team. An empty gap here means the members already cover
        the stack, not that the team declared nothing - so there is nothing left
        to contribute and fill must be 0.
        """
        result = score_team(["rust"], ["react"], member_skills=["react"])
        assert result["team_gap"] == []
        assert result["fill_pct"] == 0.0
        assert result["score"] == 0.0

    def test_team_that_declared_nothing_falls_back_to_familiarity(self):
        """
        The other kind of empty gap: no stack and no wish list, so there is no
        information to score against. Falling back to familiarity is right;
        scoring it as a full gap-fill would invent a preference.
        """
        result = score_team(["react"], [], wanted=[], member_skills=[])
        assert result["fill_pct"] == result["overlap_pct"]
        assert result["fill_pct"] == 0.0  # jaccard against an empty stack is 0

        familiar = score_team(["react"], ["react"], wanted=[], member_skills=[])
        assert familiar["fill_pct"] == 100.0

    def test_weights_favour_gap_filling(self):
        result = score_team(["nodejs"], ["react", "python"], wanted=["nodejs"])
        expected = round(0.85 * result["fill_pct"] + 0.15 * result["overlap_pct"], 1)
        assert result["score"] == expected


class TestReason:
    def test_reason_names_what_you_bring(self):
        result = score_team(["python"], ["react", "python"], member_skills=["react"])
        assert "You bring python" in result["reason"]
        assert "completes their stack" in result["reason"]

    def test_reason_reports_remaining_gaps(self):
        result = score_team(["python"], ["react", "python", "ml"], wanted=["gcp"])
        assert "still missing" in result["reason"]

    def test_reason_admits_covered_stack(self):
        result = score_team(["react"], ["react"], member_skills=["react"])
        assert result["reason"] == "Their stack is already covered"

    def test_reason_admits_nothing_useful(self):
        result = score_team(["rust"], ["react", "python"])
        assert result["reason"] == "Nothing in their gap yet"