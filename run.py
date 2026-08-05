import argparse
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from metrics import calculate_dts_error_grid, calculate_rmse, calculate_mard


# Each competition format has its own data folder. The live leaderboard ships the
# held-out targets so submissions can be scored locally; the annual competition keeps
# its targets secret, so we can only validate a submission's format against the template.
COMPETITIONS = {
    "live":   {"dir": Path("data/live_leaderboard"),   "scored": True},
    "annual": {"dir": Path("data/annual_competition"), "scored": False},
}

SUBMIT_URL = "https://huggingface.co/spaces/MetabonetBench/leaderboard-space"


def validate_predictions_format(predictions_df, template_df):
    """
    Validate that predictions match the template format exactly.
    Returns (is_valid, error_message)
    """
    errors = []
    
    if len(predictions_df) != len(template_df):
        errors.append(f"Row count mismatch: Expected {len(template_df)} rows, got {len(predictions_df)} rows")
    
    required_cols = ['id', 'source_file', 'date', 'pred_30', 'pred_60', 'pred_90', 'pred_120']
    missing_cols = [col for col in required_cols if col not in predictions_df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {', '.join(missing_cols)}")
    
    if not errors and len(predictions_df) == len(template_df):
        id_match = (predictions_df['id'].values == template_df['id'].values).all()
        source_match = (predictions_df['source_file'].values == template_df['source_file'].values).all()
        date_match = (predictions_df['date'].values == template_df['date'].values).all()
        
        if not id_match:
            errors.append("Row IDs do not match the template")
        if not source_match:
            errors.append("Source files do not match the template")
        if not date_match:
            errors.append("Dates do not match the template")
        
        if id_match and source_match and date_match:
            for i in range(min(5, len(predictions_df))):
                pred_row = predictions_df.iloc[i]
                temp_row = template_df.iloc[i]
                if (pred_row['id'] != temp_row['id'] or 
                    pred_row['source_file'] != temp_row['source_file'] or 
                    pred_row['date'] != temp_row['date']):
                    errors.append(f"Row order mismatch at row {i+1}")
                    break
    
    pred_columns = ['pred_30', 'pred_60', 'pred_90', 'pred_120']
    populated_cols = []
    has_partial = False
    for col in pred_columns:
        if col not in predictions_df.columns:
            continue
        n_total = len(predictions_df)
        n_nan = int(predictions_df[col].isna().sum())
        if n_nan == 0:
            populated_cols.append(col)
        elif n_nan == n_total:
            continue
        else:
            has_partial = True
            errors.append(
                f"Column '{col}' is partially populated "
                f"({n_nan:,} of {n_total:,} values are NaN). "
                f"Each prediction column must be either fully populated or left entirely empty."
            )

    if not missing_cols and not populated_cols and not has_partial:
        errors.append(
            "No prediction columns are populated. "
            "You must fully populate at least one of: pred_30, pred_60, pred_90, pred_120."
        )

    if errors:
        return False, "\n".join(errors)
    return True, None


def calculate_metrics(predictions_df, targets_df, horizon='60'):
    """
    Calculate metrics for specified prediction horizon(s).
    
    Args:
        predictions_df: DataFrame with prediction columns
        targets_df: DataFrame with target columns
        horizon: '30', '60', '90', '120', or 'all'
    """
    results = {}
    
    if horizon == 'all':
        # Calculate individual metrics for each horizon
        horizons = [30, 60, 90, 120]
        all_preds = []
        all_targets = []
        
        for h in horizons:
            pred_col = f'pred_{h}'
            target_col = f'target_{h}'
            
            if pred_col not in predictions_df.columns or target_col not in targets_df.columns:
                continue

            if predictions_df[pred_col].isna().all():
                continue

            pred_values = predictions_df[pred_col].values
            target_values = targets_df[target_col].values

            # Store for overall calculation
            all_preds.extend(pred_values)
            all_targets.extend(target_values)
            
            # Calculate individual horizon metrics
            rmse = calculate_rmse(pred_values, target_values)
            mard = calculate_mard(pred_values, target_values)
            dts_zones = calculate_dts_error_grid(pred_values, target_values)

            results[f'{h}_min'] = {
                'RMSE': rmse,
                'MARD': mard,
                'DTS_A': dts_zones['DTS_A_ZONE_PERCENT'],
                'DTS_B': dts_zones['DTS_B_ZONE_PERCENT'],
                'DTS_C': dts_zones['DTS_C_ZONE_PERCENT'],
                'DTS_D': dts_zones['DTS_D_ZONE_PERCENT'],
                'DTS_E': dts_zones['DTS_E_ZONE_PERCENT']
            }
        
        # Calculate overall metrics
        if all_preds and all_targets:
            overall_rmse = calculate_rmse(all_preds, all_targets)
            overall_mard = calculate_mard(all_preds, all_targets)
            overall_dts = calculate_dts_error_grid(all_preds, all_targets)

            results['overall'] = {
                'RMSE': overall_rmse,
                'MARD': overall_mard,
                'DTS_A': overall_dts['DTS_A_ZONE_PERCENT'],
                'DTS_B': overall_dts['DTS_B_ZONE_PERCENT'],
                'DTS_C': overall_dts['DTS_C_ZONE_PERCENT'],
                'DTS_D': overall_dts['DTS_D_ZONE_PERCENT'],
                'DTS_E': overall_dts['DTS_E_ZONE_PERCENT']
            }
    else:
        # Calculate metrics for single horizon
        pred_col = f'pred_{horizon}'
        target_col = f'target_{horizon}'
        
        if pred_col not in predictions_df.columns:
            raise ValueError(f"Prediction column '{pred_col}' not found")
        if target_col not in targets_df.columns:
            raise ValueError(f"Target column '{target_col}' not found")

        if predictions_df[pred_col].isna().all():
            raise ValueError(
                f"Cannot evaluate horizon {horizon}: column '{pred_col}' is empty in your predictions. "
                f"Choose a horizon you've populated, or use 'all' to evaluate every populated horizon."
            )

        pred_values = predictions_df[pred_col].values
        target_values = targets_df[target_col].values
        
        rmse = calculate_rmse(pred_values, target_values)
        mard = calculate_mard(pred_values, target_values)
        dts_zones = calculate_dts_error_grid(pred_values, target_values)

        results[f'{horizon}_min'] = {
            'RMSE': rmse,
            'MARD': mard,
            'DTS_A': dts_zones['DTS_A_ZONE_PERCENT'],
            'DTS_B': dts_zones['DTS_B_ZONE_PERCENT'],
            'DTS_C': dts_zones['DTS_C_ZONE_PERCENT'],
            'DTS_D': dts_zones['DTS_D_ZONE_PERCENT'],
            'DTS_E': dts_zones['DTS_E_ZONE_PERCENT']
        }
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Validate (and, for the live leaderboard, score) MetaboNet glucose predictions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run.py my_predictions.parquet --competition live                # live leaderboard, 60-min horizon\n"
            "  python run.py my_predictions.parquet --competition live --horizon 30    # live leaderboard, 30-min horizon\n"
            "  python run.py my_predictions.parquet --competition live --horizon all   # live leaderboard, all horizons\n"
            "  python run.py my_predictions.parquet --competition annual              # annual competition, validate format only"
        ),
    )
    parser.add_argument("predictions_file", type=Path,
                        help="Path to your predictions parquet file")
    parser.add_argument("--competition", required=True, choices=sorted(COMPETITIONS),
                        help="Which competition format to validate against (required)")
    parser.add_argument("--horizon", default="60",
                        choices=["30", "60", "90", "120", "all"],
                        help="Prediction horizon to score (live leaderboard only; default: 60)")
    args = parser.parse_args()

    predictions_file = args.predictions_file
    competition = COMPETITIONS[args.competition]
    scored = competition["scored"]
    horizon = args.horizon

    if not predictions_file.exists():
        print(f"❌ Error: File '{predictions_file}' not found")
        sys.exit(1)

    if not predictions_file.suffix == '.parquet':
        print(f"❌ Error: File must be in parquet format")
        sys.exit(1)

    # The annual competition keeps its targets secret, so there is nothing to score against.
    if not scored and args.horizon != "60":
        print(f"ℹ️  The '{args.competition}' competition validates format only — ignoring horizon '{horizon}'.")

    template_file = competition["dir"] / "template.parquet"
    targets_file = competition["dir"] / "targets.parquet"

    if not template_file.exists():
        print(f"❌ Error: Template file '{template_file}' not found")
        sys.exit(1)

    if scored and not targets_file.exists():
        print(f"❌ Error: Targets file '{targets_file}' not found")
        sys.exit(1)

    try:
        print("🔍 Loading files...")
        predictions_df = pd.read_parquet(predictions_file)
        template_df = pd.read_parquet(template_file)
        targets_df = pd.read_parquet(targets_file) if scored else None

        print("✅ Files loaded successfully")

    except Exception as e:
        print(f"❌ Error loading files: {e}")
        sys.exit(1)

    print("\n📋 Validating format...")
    is_valid, error_msg = validate_predictions_format(predictions_df, template_df)

    if not is_valid:
        print(f"\n❌ FORMAT VALIDATION FAILED:\n")
        print(error_msg)
        print("\n⚠️ Critical Requirements:")
        print("• Exact Row Matching: Your submission must have the exact same rows (id, source_file, date) as the template")
        print("• Same Order: Rows must be in identical order to the template file")
        print("• All Columns Present: Include all four columns — pred_30, pred_60, pred_90, pred_120")
        print("• At Least One Horizon Populated: Fully populate at least one of the four prediction columns")
        print("• All-or-Nothing per Column: Each populated column must have NO NaN values; horizons you skip must be left entirely empty (all NaN)")
        print("• No Extra/Missing Rows: Do not add or remove any rows from the template")
        sys.exit(1)

    print("✅ Format validation passed!")
    populated_pred_cols = [c for c in ['pred_30', 'pred_60', 'pred_90', 'pred_120']
                           if c in predictions_df.columns and not predictions_df[c].isna().any()]
    print(f"   Populated horizons: {', '.join(populated_pred_cols)}")

    # The annual competition can only validate format — targets are secret, so we stop here.
    if not scored:
        print("\n" + "="*60)
        print("\n✅ Format is valid! You are ready to submit!")
        print("   (Annual competition: scoring runs server-side against secret targets.)")
        print("🚀 Submit your predictions at:")
        print(f"   {SUBMIT_URL}")
        print("\n" + "="*60)
        return

    print(f"\n📊 Calculating metrics for horizon: {horizon}...")
    try:
        metrics = calculate_metrics(predictions_df, targets_df, horizon)
    except ValueError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    print("\n" + "="*60)
    print("                    EVALUATION RESULTS")
    print("="*60)

    # Display metrics based on what was calculated
    for horizon_key, horizon_metrics in metrics.items():
        if horizon_key == 'overall':
            print(f"\n📊 OVERALL METRICS (All Horizons Combined):")
        else:
            print(f"\n📈 {horizon_key.replace('_', ' ').title()} Ahead Predictions:")

        print(f"   RMSE: {horizon_metrics['RMSE']:.2f} mg/dL")
        print(f"   MARD: {horizon_metrics['MARD']:.2f} %")
        print(f"\n   DTS Error Grid Zones:")
        print(f"   • Zone A (No Risk):        {horizon_metrics['DTS_A']:.1f}%")
        print(f"   • Zone B (Mild Risk):      {horizon_metrics['DTS_B']:.1f}%")
        print(f"   • Zone C (Moderate Risk):  {horizon_metrics['DTS_C']:.1f}%")
        print(f"   • Zone D (High Risk):      {horizon_metrics['DTS_D']:.1f}%")
        print(f"   • Zone E (Extreme Risk):   {horizon_metrics['DTS_E']:.1f}%")

    print("\n" + "="*60)
    print("\n✅ Format is valid! You are ready to submit!")
    print("🚀 Submit your predictions at:")
    print(f"   {SUBMIT_URL}")
    print("\n" + "="*60)


if __name__ == "__main__":
    main()
