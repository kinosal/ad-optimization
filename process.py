import datetime
import numpy as np
import pandas as pd


def preprocess(data, impression_weight=None, engagement_weight=None,
               click_weight=None, conversion_weight=None):
    """
    Prepare dataframe from CSV with channel (optional), date, ad_id,
    impressions, engagements, clicks and conversions
    for bandit optimization
    """

    # Standardize column name input format
    data.columns = \
        [column.lower().replace(" ", "_") for column in data.columns]

    # Rename columns from Facebook export
    data.rename(columns={'reporting_ends': 'date'}, inplace=True)
    data.rename(columns={'amount_spent_(eur)': 'cost'}, inplace=True)
    data.rename(columns={'post_engagement': 'engagements'}, inplace=True)
    data.rename(columns={'link_clicks': 'clicks'}, inplace=True)
    data.rename(columns={'purchases': 'conversions'}, inplace=True)
    if 'reporting_starts' in data.columns:
        data.drop(['reporting_starts'], axis='columns', inplace=True)

    # Rename columns from Google export
    data.rename(columns={'day': 'date'}, inplace=True)
    if 'currency' in data.columns:
        data.drop(['currency'], axis='columns', inplace=True)

    # Set relevant empty and NaN values to 0 for calculations
    data = data.replace('', np.nan)
    for column in ['cost', 'impressions', 'engagements', 'clicks',
                   'conversions']:
        data[column].fillna(value=0.0, downcast='infer', inplace=True)

    # Remove rows with 0 cost (ads that did not run)
    data = data[data['cost'] != 0]

    # If not provided, set weights to respective cost ratios
    weights = {}
    for weight in ['impression', 'engagement', 'click', 'conversion']:
        if locals()[weight + '_weight'] is None:
            if data[weight + 's'].sum() == 0:
                weights[weight + '_weight'] = 0
            else:
                weights[weight + '_weight'] = \
                    data['cost'].sum() * 100 / data[weight + 's'].sum()
        else:
            weights[weight + '_weight'] = locals()[weight + '_weight']

    # Create successes column as weighted sum of success metrics
    data['successes'] = [row['impressions'] * weights['impression_weight'] +
                         row['engagements'] * weights['engagement_weight'] +
                         row['clicks'] * weights['click_weight'] +
                         row['conversions'] * weights['conversion_weight']
                         for index, row in data.iterrows()]

    # Create trials column as costs in cents + successes + 1
    # to guarantee successes <= trials and correct for free impressions
    data['trials'] = [int(row['cost'] * 100) + row['successes'] + 1
                      for index, row in data.iterrows()]

    # Drop processed columns
    drop = ['cost', 'impressions', 'engagements', 'clicks', 'conversions']
    data.drop(drop, axis='columns', inplace=True)

    # Only keep necessary columns
    # Does not comply with API consumption at this point,
    # Revise later in coordination with API consumers

    # keep = ['ad_id', 'date', 'trials', 'successes']
    # data.drop(data.columns.difference(keep), axis='columns', inplace=True)

    # Drop all rows with remaining NaN values (e.g. missing ad_id)
    data.dropna(axis=0, how='any', inplace=True)

    return data


def filter_dates(data, cutoff):
    """Return data with dates in cutoff range"""
    data['date'] = pd.to_datetime(data['date'], format='%Y-%m-%d').dt.date
    data = data.loc[data['date'] >=
                    datetime.date.today() - datetime.timedelta(days=cutoff)]
    return data


def reindex_options(data):
    """
    Process dataframe with ad_id, date, trials and successes;
    return options and dataframe with option id column
    """
    combinations = data.drop(['date', 'trials', 'successes'], axis='columns')
    options = combinations.drop_duplicates().reset_index() \
                          .drop('index', axis='columns')
    data['option_id'] = 0
    for i in range(len(data)):
        data.at[i, 'option_id'] = \
            options.loc[options['ad_id'] == data.iloc[i]['ad_id']].index[0]
    return [options, data]
