import numpy as np
import pandas as pd
from diff_diff import SyntheticDiD
from diff_diff.prep import balance_panel

VALID_BALANCE_METHODS = {'inner', 'fill'}


def extract_sdid_weight_tables(result):
    try:
        unit_weights_df = result.get_unit_weights_df().copy().sort_values('weight', ascending=False).reset_index(drop=True)
    except Exception:
        unit_weights_df = pd.DataFrame(columns=['unit', 'weight'])
    try:
        time_weights_df = result.get_time_weights_df().copy().sort_values('weight', ascending=False).reset_index(drop=True)
    except Exception:
        time_weights_df = pd.DataFrame(columns=['period', 'weight'])
    return unit_weights_df, time_weights_df


def compute_sdid_pre_fit_diagnostics(panel_balanced, unit_weights_df, post_period_list):
    diagnostics = {
        'pre_gap_mean': np.nan,
        'pre_gap_rmse': np.nan,
        'pre_gap_slope': np.nan,
        'treated_pre_std': np.nan,
        'poor_pre_fit': None,
    }
    if panel_balanced.empty or unit_weights_df is None or unit_weights_df.empty:
        return diagnostics

    uw = unit_weights_df[['unit', 'weight']].copy()
    panel = panel_balanced.merge(uw, left_on='unit_id', right_on='unit', how='left')
    panel['weight'] = panel['weight'].fillna(0.0)

    treated_ts = panel[panel['treated'] == 1].groupby('year_quarter')['log_price'].mean()
    control_panel = panel[panel['treated'] == 0].copy()
    control_panel['weighted_outcome'] = control_panel['log_price'] * control_panel['weight']
    synthetic_ts = control_panel.groupby('year_quarter')['weighted_outcome'].sum()
    common_idx = treated_ts.index.intersection(synthetic_ts.index)
    if len(common_idx) == 0:
        return diagnostics

    post_periods = set(post_period_list)
    pre_idx = [t for t in common_idx if t not in post_periods]
    if not pre_idx:
        return diagnostics

    treated_pre = treated_ts.loc[pre_idx].astype(float)
    synthetic_pre = synthetic_ts.loc[pre_idx].astype(float)
    gap_pre = treated_pre.values - synthetic_pre.values
    treated_pre_std = float(np.std(treated_pre.values))
    pre_gap_rmse = float(np.sqrt(np.mean(gap_pre ** 2)))

    diagnostics.update({
        'pre_gap_mean': float(np.mean(gap_pre)),
        'pre_gap_rmse': pre_gap_rmse,
        'treated_pre_std': treated_pre_std,
        'poor_pre_fit': pre_gap_rmse > treated_pre_std,
    })
    if len(gap_pre) >= 2:
        diagnostics['pre_gap_slope'] = float(np.polyfit(np.arange(len(gap_pre)), gap_pre, 1)[0])
    return diagnostics


def print_sdid_weight_tables(unit_weights_df, time_weights_df):
    if unit_weights_df is not None and not unit_weights_df.empty:
        print('  Unit weights:')
        print(unit_weights_df.to_string(index=False))
    else:
        print('  Unit weights: unavailable')
    if time_weights_df is not None and not time_weights_df.empty:
        print('  Time weights:')
        print(time_weights_df.to_string(index=False))
    else:
        print('  Time weights: unavailable')


def _balance_prepared_panel(panel_ready, balance_method='inner', fill_value=None):
    if balance_method not in VALID_BALANCE_METHODS:
        raise ValueError(f"balance_method must be one of {sorted(VALID_BALANCE_METHODS)}, got '{balance_method}'")

    if panel_ready.empty:
        return pd.DataFrame(), pd.DataFrame()

    if balance_method == 'inner':
        panel_balanced = balance_panel(
            data=panel_ready,
            unit_column='unit_id',
            time_column='year_quarter',
            method='inner',
        )
        return panel_balanced, pd.DataFrame(columns=['unit_id', 'year_quarter', 'balance_fill_source'])

    all_units = sorted(panel_ready['unit_id'].unique())
    all_periods = sorted(panel_ready['year_quarter'].unique())
    full_grid = pd.MultiIndex.from_product([all_units, all_periods], names=['unit_id', 'year_quarter']).to_frame(index=False)
    panel_full = full_grid.merge(panel_ready, on=['unit_id', 'year_quarter'], how='left', indicator=True)
    balance_fill_rows = panel_full.loc[
        panel_full['_merge'].eq('left_only'),
        ['unit_id', 'year_quarter'],
    ].copy()
    balance_fill_rows['balance_fill_source'] = 'balance_panel_fill'

    panel_balanced = balance_panel(
        data=panel_ready,
        unit_column='unit_id',
        time_column='year_quarter',
        method='fill',
        fill_value=fill_value,
    )

    unit_treated = panel_ready.groupby('unit_id')['treated'].max()
    period_post = panel_ready.groupby('year_quarter')['post'].max()
    panel_balanced['treated'] = panel_balanced['unit_id'].map(unit_treated).astype(int)
    panel_balanced['post'] = panel_balanced['year_quarter'].map(period_post).astype(int)

    return panel_balanced, balance_fill_rows.sort_values(['unit_id', 'year_quarter']).reset_index(drop=True)


def fit_prepared_diffdiff_panel(panel_balanced, covariate_cols):
    if panel_balanced.empty:
        return {'skip_reason': 'empty balanced panel'}
    balanced_unit_treatment = panel_balanced[['unit_id', 'treated']].drop_duplicates()
    n_treated_units = int((balanced_unit_treatment['treated'] == 1).sum())
    n_control_units = int((balanced_unit_treatment['treated'] == 0).sum())
    n_periods = int(panel_balanced['year_quarter'].nunique())
    if n_treated_units == 0 or n_control_units == 0:
        return {'skip_reason': 'balanced panel lacks treated or control units', 'n_treated_units': n_treated_units, 'n_control_units': n_control_units, 'n_periods': n_periods}
    all_periods = sorted(panel_balanced['year_quarter'].unique().tolist())
    post_period_list = sorted(panel_balanced.loc[panel_balanced['post'] == 1, 'year_quarter'].unique().tolist())
    pre_period_list = [p for p in all_periods if p not in set(post_period_list)]
    if not post_period_list:
        return {'skip_reason': 'no post periods', 'n_treated_units': n_treated_units, 'n_control_units': n_control_units, 'n_periods': n_periods, 'n_pre_periods': len(pre_period_list), 'n_post_periods': 0}
    if not pre_period_list:
        return {
            'skip_reason': 'no pre periods after balancing',
            'n_treated_units': n_treated_units,
            'n_control_units': n_control_units,
            'n_periods': n_periods,
            'n_pre_periods': 0,
            'n_post_periods': len(post_period_list),
            'all_periods': all_periods,
            'post_periods': post_period_list,
        }
    fit_covariates = [c for c in covariate_cols if c in panel_balanced.columns and panel_balanced[c].notna().all()]
    dropped_covariates = sorted(set(covariate_cols) - set(fit_covariates))
    sdid = SyntheticDiD(variance_method='bootstrap', alpha=0.05)
    fit_kwargs = dict(data=panel_balanced, outcome='log_price', treatment='treated', unit='unit_id', time='year_quarter', post_periods=post_period_list)
    if fit_covariates:
        fit_kwargs['covariates'] = fit_covariates
    result = sdid.fit(**fit_kwargs)
    tau = result.att
    unit_weights_df, time_weights_df = extract_sdid_weight_tables(result)
    pre_fit = compute_sdid_pre_fit_diagnostics(panel_balanced, unit_weights_df, post_period_list)
    return {'skip_reason': None, 'res': result, 'att': tau, 'se': result.se, 'pct_effect': (np.exp(tau) - 1) * 100, 'p_value': result.p_value, 'conf_int': result.conf_int, 'fit_covariates': fit_covariates, 'dropped_covariates': dropped_covariates, 'post_periods': post_period_list, 'pre_periods': pre_period_list, 'panel_balanced': panel_balanced.copy(), 'n_treated_units': n_treated_units, 'n_control_units': n_control_units, 'n_periods': n_periods, 'n_pre_periods': len(pre_period_list), 'n_post_periods': len(post_period_list), 'unit_weights_df': unit_weights_df.copy(), 'time_weights_df': time_weights_df.copy(), **pre_fit}


def prepare_no_imputation_panel(sdid_panel, covariate_cols, balance_method='inner', fill_value=None):
    panel_ready = sdid_panel[['unit_id', 'year_quarter', 'treated', 'post', 'log_price'] + covariate_cols].copy()
    panel_balanced, balance_fill_rows = _balance_prepared_panel(
        panel_ready,
        balance_method=balance_method,
        fill_value=fill_value,
    )
    return {'panel_full': pd.DataFrame(), 'panel_balanced': panel_balanced, 'imputed_rows_df': balance_fill_rows, 'dropped_units_df': pd.DataFrame()}


def prepare_half_year_panel(sdid_panel, covariate_cols, balance_method='inner', fill_value=None):
    impute_cols = ['log_price', 'treated', 'post'] + covariate_cols
    all_units = sorted(sdid_panel['unit_id'].unique())
    all_periods = sorted(sdid_panel['year_quarter'].unique())
    full_grid = pd.MultiIndex.from_product([all_units, all_periods], names=['unit_id', 'year_quarter']).to_frame(index=False)
    panel_full = full_grid.merge(sdid_panel, on=['unit_id', 'year_quarter'], how='left', indicator=True)
    panel_full['was_missing'] = panel_full['_merge'].eq('left_only')
    panel_full['year'] = panel_full['year_quarter'].str[:4]
    panel_full['quarter_num'] = panel_full['year_quarter'].str.extract(r'Q([1-4])').astype(int)
    panel_full['half'] = np.where(panel_full['quarter_num'].isin([1, 2]), 'H1', 'H2')
    panel_full['year_half'] = panel_full['year'] + '-' + panel_full['half']
    panel_full['observed_flag'] = (~panel_full['was_missing']).astype(int)
    obs_per_half = panel_full.groupby(['unit_id', 'year_half'])['observed_flag'].transform('sum')
    panel_full['eligible_half_impute'] = (obs_per_half >= 1) & (obs_per_half < 2)
    for col in impute_cols:
        panel_full[f'{col}_half_fill'] = panel_full.groupby(['unit_id', 'year_half'])[col].transform(lambda s: s.ffill().bfill())
        panel_full.loc[panel_full['was_missing'] & panel_full['eligible_half_impute'], col] = panel_full.loc[panel_full['was_missing'] & panel_full['eligible_half_impute'], f'{col}_half_fill']
    panel_full['was_imputed'] = panel_full['was_missing'] & panel_full['log_price'].notna()
    panel_ready = panel_full.loc[panel_full['log_price'].notna(), ['unit_id', 'year_quarter', 'treated', 'post', 'log_price'] + covariate_cols].copy()
    panel_balanced, balance_fill_rows = _balance_prepared_panel(
        panel_ready,
        balance_method=balance_method,
        fill_value=fill_value,
    )
    imputed_rows_df = panel_full.loc[panel_full['was_imputed'], ['unit_id', 'year_quarter', 'year_half']].sort_values(['unit_id', 'year_quarter'])
    if not balance_fill_rows.empty:
        imputed_rows_df = pd.concat([imputed_rows_df, balance_fill_rows], ignore_index=True, sort=False)
    return {'panel_full': panel_full, 'panel_balanced': panel_balanced, 'imputed_rows_df': imputed_rows_df, 'dropped_units_df': pd.DataFrame()}


def _prepare_single_gap_linear_panel(sdid_panel, covariate_cols, group_cols, extra_imputed_cols, balance_method='inner', fill_value=None):
    impute_cols = ['log_price'] + covariate_cols
    all_units = sorted(sdid_panel['unit_id'].unique())
    all_periods = sorted(sdid_panel['year_quarter'].unique())
    full_grid = pd.MultiIndex.from_product([all_units, all_periods], names=['unit_id', 'year_quarter']).to_frame(index=False)
    panel_full = full_grid.merge(sdid_panel, on=['unit_id', 'year_quarter'], how='left', indicator=True)
    panel_full['was_missing'] = panel_full['_merge'].eq('left_only')
    panel_full['year'] = panel_full['year_quarter'].str[:4]
    panel_full['quarter_num'] = panel_full['year_quarter'].str.extract(r'Q([1-4])').astype(int)
    period_post = sdid_panel.groupby('year_quarter')['post'].max()
    unit_treated = sdid_panel.groupby('unit_id')['treated'].max()
    panel_full['post'] = panel_full['year_quarter'].map(period_post).astype(int)
    panel_full['treated'] = panel_full['unit_id'].map(unit_treated).astype(int)
    panel_full['time_id'] = panel_full['year_quarter'].map({p: i for i, p in enumerate(all_periods)}).astype(int)
    panel_full = panel_full.sort_values(['unit_id', 'time_id']).reset_index(drop=True)

    def _interpolate_group(group):
        group = group.sort_values('time_id').copy()
        missing = group['was_missing'].fillna(False).to_numpy()
        run_len = np.zeros(len(group), dtype=int)
        eligible = np.zeros(len(group), dtype=bool)
        i = 0
        while i < len(group):
            if missing[i]:
                j = i
                while j < len(group) and missing[j]:
                    j += 1
                current_run = j - i
                run_len[i:j] = current_run
                has_prev_obs = i > 0 and not missing[i - 1]
                has_next_obs = j < len(group) and not missing[j]
                if current_run == 1 and has_prev_obs and has_next_obs:
                    eligible[i:j] = True
                i = j
            else:
                i += 1
        group['missing_run_len'] = run_len
        group['eligible_single_gap_impute'] = eligible
        for col in impute_cols:
            interpolated = pd.to_numeric(group[col], errors='coerce').interpolate(method='linear', limit_area='inside')
            group.loc[group['eligible_single_gap_impute'], col] = interpolated.loc[group['eligible_single_gap_impute']]
        return group

    panel_full = panel_full.groupby(group_cols, group_keys=False).apply(_interpolate_group).reset_index(drop=True)
    panel_full['was_imputed'] = panel_full['was_missing'] & panel_full['eligible_single_gap_impute'] & panel_full['log_price'].notna()

    panel_ready = panel_full.loc[
        panel_full['log_price'].notna(),
        ['unit_id', 'year_quarter', 'treated', 'post', 'log_price'] + covariate_cols,
    ].copy()
    panel_balanced, balance_fill_rows = _balance_prepared_panel(
        panel_ready,
        balance_method=balance_method,
        fill_value=fill_value,
    )

    imputed_rows_df = panel_full.loc[
        panel_full['was_imputed'],
        ['unit_id', 'year_quarter'] + extra_imputed_cols,
    ].sort_values(['unit_id', 'year_quarter'])
    if not balance_fill_rows.empty:
        imputed_rows_df = pd.concat([imputed_rows_df, balance_fill_rows], ignore_index=True, sort=False)
    return {'panel_full': panel_full, 'panel_balanced': panel_balanced, 'imputed_rows_df': imputed_rows_df, 'dropped_units_df': pd.DataFrame()}


def prepare_single_gap_panel(sdid_panel, covariate_cols, balance_method='inner', fill_value=None):
    return _prepare_single_gap_linear_panel(
        sdid_panel,
        covariate_cols,
        group_cols=['unit_id', 'post'],
        extra_imputed_cols=['post', 'missing_run_len'],
        balance_method=balance_method,
        fill_value=fill_value,
    )


def prepare_single_gap_year_panel(sdid_panel, covariate_cols, balance_method='inner', fill_value=None):
    return _prepare_single_gap_linear_panel(
        sdid_panel,
        covariate_cols,
        group_cols=['unit_id', 'year', 'post'],
        extra_imputed_cols=['year', 'post', 'missing_run_len'],
        balance_method=balance_method,
        fill_value=fill_value,
    )


def prepare_whole_year_panel(sdid_panel, covariate_cols, balance_method='inner', fill_value=None):
    all_units = sorted(sdid_panel['unit_id'].unique())
    all_periods = sorted(sdid_panel['year_quarter'].unique())
    full_grid = pd.MultiIndex.from_product([all_units, all_periods], names=['unit_id', 'year_quarter']).to_frame(index=False)
    panel_full = full_grid.merge(sdid_panel, on=['unit_id', 'year_quarter'], how='left', indicator=True)
    panel_full['was_missing'] = panel_full['_merge'].eq('left_only')
    panel_full['year'] = panel_full['year_quarter'].str[:4]
    panel_full['observed_flag'] = (~panel_full['was_missing']).astype(int)
    obs_per_year = panel_full.groupby(['unit_id', 'year'])['observed_flag'].transform('sum')
    panel_full['eligible_year_impute'] = obs_per_year >= 1
    for col in ['log_price'] + covariate_cols:
        panel_full[f'{col}_year_fill'] = panel_full.groupby(['unit_id', 'year'])[col].transform('mean')
        panel_full.loc[panel_full['was_missing'] & panel_full['eligible_year_impute'], col] = panel_full.loc[panel_full['was_missing'] & panel_full['eligible_year_impute'], f'{col}_year_fill']
    panel_full['treated_year_fill'] = panel_full.groupby(['unit_id', 'year'])['treated'].transform('max')
    panel_full['post_year_fill'] = panel_full.groupby(['unit_id', 'year'])['post'].transform('max')
    panel_full.loc[panel_full['was_missing'] & panel_full['eligible_year_impute'], 'treated'] = panel_full.loc[panel_full['was_missing'] & panel_full['eligible_year_impute'], 'treated_year_fill']
    panel_full.loc[panel_full['was_missing'] & panel_full['eligible_year_impute'], 'post'] = panel_full.loc[panel_full['was_missing'] & panel_full['eligible_year_impute'], 'post_year_fill']
    panel_full['was_imputed'] = panel_full['was_missing'] & panel_full['log_price'].notna()
    panel_ready = panel_full.loc[panel_full['log_price'].notna(), ['unit_id', 'year_quarter', 'treated', 'post', 'log_price'] + covariate_cols].copy()
    panel_balanced, balance_fill_rows = _balance_prepared_panel(
        panel_ready,
        balance_method=balance_method,
        fill_value=fill_value,
    )
    imputed_rows_df = panel_full.loc[panel_full['was_imputed'], ['unit_id', 'year_quarter', 'year']].sort_values(['unit_id', 'year_quarter'])
    if not balance_fill_rows.empty:
        imputed_rows_df = pd.concat([imputed_rows_df, balance_fill_rows], ignore_index=True, sort=False)
    return {'panel_full': panel_full, 'panel_balanced': panel_balanced, 'imputed_rows_df': imputed_rows_df, 'dropped_units_df': pd.DataFrame()}


def prepare_gap_panel(sdid_panel, covariate_cols, max_allowed_missing_run, balance_method='inner', fill_value=None):
    all_units = sorted(sdid_panel['unit_id'].unique())
    all_periods = sorted(sdid_panel['year_quarter'].unique())
    full_grid = pd.MultiIndex.from_product([all_units, all_periods], names=['unit_id', 'year_quarter']).to_frame(index=False)
    panel_full = full_grid.merge(sdid_panel, on=['unit_id', 'year_quarter'], how='left', indicator=True)
    panel_full['was_missing'] = panel_full['_merge'].eq('left_only')
    panel_full['time_id'] = panel_full['year_quarter'].map({p: i for i, p in enumerate(all_periods)}).astype(int)
    panel_full = panel_full.sort_values(['unit_id', 'time_id']).reset_index(drop=True)
    def _annotate(group):
        missing = group['was_missing'].fillna(False).to_numpy()
        run_len = np.zeros(len(group), dtype=int)
        max_run = 0
        i = 0
        while i < len(group):
            if missing[i]:
                j = i
                while j < len(group) and missing[j]:
                    j += 1
                current_run = j - i
                run_len[i:j] = current_run
                max_run = max(max_run, current_run)
                i = j
            else:
                i += 1
        out = group.copy()
        out['missing_run_len'] = run_len
        out['max_missing_run'] = max_run
        return out
    panel_full = panel_full.groupby('unit_id', group_keys=False).apply(_annotate).reset_index(drop=True)
    dropped_units_df = panel_full.groupby('unit_id', as_index=False).agg(max_missing_run=('missing_run_len', 'max'), n_missing_rows=('was_missing', 'sum'))
    dropped_units_df = dropped_units_df[dropped_units_df['max_missing_run'] > max_allowed_missing_run].sort_values(['max_missing_run', 'unit_id'], ascending=[False, True]).reset_index(drop=True)
    panel_kept = panel_full[~panel_full['unit_id'].isin(dropped_units_df['unit_id'])].copy()
    panel_kept['treated'] = panel_kept.groupby('unit_id')['treated'].transform('max')
    panel_kept['post'] = panel_kept.groupby('year_quarter')['post'].transform('max')
    for col in ['log_price'] + covariate_cols:
        panel_kept[col] = panel_kept.groupby('unit_id')[col].transform(lambda s: s.interpolate(method='linear', limit_direction='both'))
    panel_kept['was_imputed'] = panel_kept['was_missing'] & panel_kept['log_price'].notna()
    panel_ready = panel_kept.loc[panel_kept['log_price'].notna(), ['unit_id', 'year_quarter', 'treated', 'post', 'log_price'] + covariate_cols].copy()
    panel_balanced, balance_fill_rows = _balance_prepared_panel(
        panel_ready,
        balance_method=balance_method,
        fill_value=fill_value,
    )
    imputed_rows_df = panel_kept.loc[panel_kept['was_imputed'], ['unit_id', 'year_quarter', 'missing_run_len']].sort_values(['unit_id', 'year_quarter'])
    if not balance_fill_rows.empty:
        imputed_rows_df = pd.concat([imputed_rows_df, balance_fill_rows], ignore_index=True, sort=False)
    return {'panel_full': panel_full, 'panel_balanced': panel_balanced, 'imputed_rows_df': imputed_rows_df, 'dropped_units_df': dropped_units_df}
