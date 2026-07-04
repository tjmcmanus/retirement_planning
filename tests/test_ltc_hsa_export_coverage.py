"""
Coverage tests for ltc_hsa_export.py.

All six export functions are tested with SimpleNamespace mock objects so no
external dependencies are required.
"""
import types
import pytest
import pandas as pd

from ltc_hsa_export import (
    export_ltc_analysis_to_csv,
    export_ltc_analysis_to_json,
    export_hsa_analysis_to_csv,
    export_hsa_analysis_to_json,
    export_ltc_analysis_to_markdown,
    export_hsa_analysis_to_markdown,
)


# ---------------------------------------------------------------------------
# Shared fixtures (SimpleNamespace mocks)
# ---------------------------------------------------------------------------

@pytest.fixture
def cost_df():
    return pd.DataFrame({
        "Care Type": ["Home Care", "Assisted Living"],
        "Monthly Cost": [4_000, 5_500],
        "Annual Cost": [48_000, 66_000],
    })


@pytest.fixture
def medicaid():
    return types.SimpleNamespace(
        current_assets=500_000.0,
        asset_limit=2_000.0,
        excess_assets=498_000.0,
        months_to_qualify=48,
        protected_spouse_assets=148_620.0,
        spend_down_strategies=["Prepay medical bills", "Fund funeral trust"],
        lookback_concerns=["Gift of $30,000 in 2022"],
    )


@pytest.fixture
def insurance():
    return types.SimpleNamespace(
        annual_premium=3_200.0,
        total_premiums_paid=96_000.0,
        daily_benefit=150.0,
        benefit_period_years=3,
        total_insurance_benefit=164_250.0,
        self_insurance_cost=180_000.0,
        break_even_year=2037,
        recommendation="Consider LTC insurance",
        notes=["Coverage starts at 90-day elimination period"],
    )


@pytest.fixture
def ltc_prob():
    return {
        "any_ltc": 0.70,
        "expected_duration_years": 2.5,
        "less_than_1_year": 0.25,
        "1_to_3_years": 0.30,
        "3_to_5_years": 0.20,
        "more_than_5_years": 0.25,
    }


@pytest.fixture
def hsa_projection():
    return types.SimpleNamespace(
        current_balance=25_000.0,
        years_to_medicare=10,
        total_contributions=50_000.0,
        investment_growth=40_000.0,
        final_balance=115_000.0,
        annual_projections=[
            {"year": 2026, "balance": 30_000},
            {"year": 2027, "balance": 36_000},
        ],
    )


@pytest.fixture
def hsa_strategy():
    return types.SimpleNamespace(
        strategy_name="Pay-As-You-Go",
        annual_medical_expenses=6_000.0,
        hsa_withdrawals=6_000.0,
        taxable_withdrawals=0.0,
        years_hsa_lasts=15,
        total_tax_savings=24_000.0,
        notes=["Best for high-deductible health plan holders"],
    )


@pytest.fixture
def hsa_tax_adv():
    return types.SimpleNamespace(
        total_contributions=50_000.0,
        tax_savings_contributions=12_500.0,
        investment_growth=40_000.0,
        tax_savings_growth=10_000.0,
        qualified_withdrawals=115_000.0,
        tax_savings_withdrawals=28_750.0,
        total_tax_advantage=51_250.0,
        equivalent_taxable_account=166_250.0,
    )


@pytest.fixture
def hsa_healthcare():
    return {
        "base_healthcare": 12_000.0,
        "medicare_premiums": 3_600.0,
        "out_of_pocket": 3_000.0,
        "long_term_care": 6_000.0,
        "total_healthcare_costs": 330_000.0,
        "annual_average": 16_500.0,
    }


# ---------------------------------------------------------------------------
# export_ltc_analysis_to_csv
# ---------------------------------------------------------------------------

class TestExportLtcAnalysisToCsv:
    def test_returns_string(self, cost_df, medicaid):
        result = export_ltc_analysis_to_csv(cost_df, medicaid)
        assert isinstance(result, str)

    def test_contains_header(self, cost_df, medicaid):
        result = export_ltc_analysis_to_csv(cost_df, medicaid)
        assert "Long-Term Care" in result

    def test_contains_medicaid_data(self, cost_df, medicaid):
        result = export_ltc_analysis_to_csv(cost_df, medicaid)
        assert "500,000" in result

    def test_insurance_section_present_when_provided(self, cost_df, medicaid, insurance):
        result = export_ltc_analysis_to_csv(cost_df, medicaid, insurance_analysis=insurance)
        assert "INSURANCE" in result.upper()

    def test_insurance_section_absent_when_not_provided(self, cost_df, medicaid):
        result = export_ltc_analysis_to_csv(cost_df, medicaid)
        assert "INSURANCE" not in result.upper()

    def test_ltc_probability_section_present(self, cost_df, medicaid, ltc_prob):
        result = export_ltc_analysis_to_csv(cost_df, medicaid, ltc_probability=ltc_prob)
        assert "PROBABILITY" in result.upper()


# ---------------------------------------------------------------------------
# export_ltc_analysis_to_json
# ---------------------------------------------------------------------------

class TestExportLtcAnalysisToJson:
    def test_returns_string(self, cost_df, medicaid):
        result = export_ltc_analysis_to_json(cost_df, medicaid)
        assert isinstance(result, str)

    def test_is_valid_json(self, cost_df, medicaid):
        import json
        result = export_ltc_analysis_to_json(cost_df, medicaid)
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_medicaid_section_present(self, cost_df, medicaid):
        import json
        result = json.loads(export_ltc_analysis_to_json(cost_df, medicaid))
        assert "medicaid_analysis" in result

    def test_insurance_section_present_when_provided(self, cost_df, medicaid, insurance):
        import json
        result = json.loads(export_ltc_analysis_to_json(
            cost_df, medicaid, insurance_analysis=insurance
        ))
        assert "insurance_analysis" in result

    def test_ltc_probability_present_when_provided(self, cost_df, medicaid, ltc_prob):
        import json
        result = json.loads(export_ltc_analysis_to_json(
            cost_df, medicaid, ltc_probability=ltc_prob
        ))
        assert "ltc_probability" in result


# ---------------------------------------------------------------------------
# export_hsa_analysis_to_csv
# ---------------------------------------------------------------------------

class TestExportHsaAnalysisToCsv:
    def test_returns_string_with_no_optional_args(self):
        result = export_hsa_analysis_to_csv(None)
        assert isinstance(result, str)

    def test_returns_string_with_projection(self, hsa_projection):
        result = export_hsa_analysis_to_csv(hsa_projection)
        assert "HSA" in result.upper()

    def test_strategies_section_present(self, hsa_projection, hsa_strategy):
        result = export_hsa_analysis_to_csv(hsa_projection, strategies=[hsa_strategy])
        assert "STRATEGIES" in result.upper() or "Pay-As-You-Go" in result

    def test_tax_advantage_section_present(self, hsa_projection, hsa_tax_adv):
        result = export_hsa_analysis_to_csv(hsa_projection, tax_advantage=hsa_tax_adv)
        assert "TAX ADVANTAGE" in result.upper() or "TRIPLE" in result.upper()

    def test_healthcare_costs_section_present(self, hsa_projection, hsa_healthcare):
        result = export_hsa_analysis_to_csv(hsa_projection, healthcare_costs=hsa_healthcare)
        assert "HEALTHCARE" in result.upper()


# ---------------------------------------------------------------------------
# export_hsa_analysis_to_json
# ---------------------------------------------------------------------------

class TestExportHsaAnalysisToJson:
    def test_returns_valid_json(self, hsa_projection):
        import json
        result = export_hsa_analysis_to_json(hsa_projection)
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_projection_section_present(self, hsa_projection):
        import json
        data = json.loads(export_hsa_analysis_to_json(hsa_projection))
        assert "projection" in data

    def test_strategies_section_present(self, hsa_projection, hsa_strategy):
        import json
        data = json.loads(export_hsa_analysis_to_json(
            hsa_projection, strategies=[hsa_strategy]
        ))
        assert "withdrawal_strategies" in data

    def test_tax_advantage_present(self, hsa_projection, hsa_tax_adv):
        import json
        data = json.loads(export_hsa_analysis_to_json(
            hsa_projection, tax_advantage=hsa_tax_adv
        ))
        assert "triple_tax_advantage" in data

    def test_healthcare_costs_present(self, hsa_projection, hsa_healthcare):
        import json
        data = json.loads(export_hsa_analysis_to_json(
            hsa_projection, healthcare_costs=hsa_healthcare
        ))
        assert "healthcare_costs" in data


# ---------------------------------------------------------------------------
# export_ltc_analysis_to_markdown
# ---------------------------------------------------------------------------

class TestExportLtcAnalysisToMarkdown:
    def test_returns_string(self, cost_df, medicaid):
        result = export_ltc_analysis_to_markdown(cost_df, medicaid)
        assert isinstance(result, str)

    def test_has_markdown_header(self, cost_df, medicaid):
        result = export_ltc_analysis_to_markdown(cost_df, medicaid)
        assert result.startswith("#")

    def test_insurance_section_present(self, cost_df, medicaid, insurance):
        result = export_ltc_analysis_to_markdown(
            cost_df, medicaid, insurance_analysis=insurance
        )
        assert "Insurance" in result

    def test_ltc_probability_section_present(self, cost_df, medicaid, ltc_prob):
        result = export_ltc_analysis_to_markdown(
            cost_df, medicaid, ltc_probability=ltc_prob
        )
        assert "Probability" in result


# ---------------------------------------------------------------------------
# export_hsa_analysis_to_markdown
# ---------------------------------------------------------------------------

class TestExportHsaAnalysisToMarkdown:
    def test_returns_string(self, hsa_projection):
        result = export_hsa_analysis_to_markdown(hsa_projection)
        assert isinstance(result, str)

    def test_has_markdown_header(self, hsa_projection):
        result = export_hsa_analysis_to_markdown(hsa_projection)
        assert result.startswith("#")

    def test_no_projection_returns_minimal_output(self):
        result = export_hsa_analysis_to_markdown(None)
        assert isinstance(result, str)

    def test_strategies_section_present(self, hsa_projection, hsa_strategy):
        result = export_hsa_analysis_to_markdown(
            hsa_projection, strategies=[hsa_strategy]
        )
        assert "Strategy" in result

    def test_tax_advantage_section_present(self, hsa_projection, hsa_tax_adv):
        result = export_hsa_analysis_to_markdown(
            hsa_projection, tax_advantage=hsa_tax_adv
        )
        assert "Tax Advantage" in result

    def test_healthcare_costs_section_present(self, hsa_projection, hsa_healthcare):
        result = export_hsa_analysis_to_markdown(
            hsa_projection, healthcare_costs=hsa_healthcare
        )
        assert "Healthcare" in result
