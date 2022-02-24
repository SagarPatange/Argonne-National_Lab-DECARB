# -*- coding: utf-8 -*-
"""
Created on Mon Jan 10 20:08:36 2022

@author: skar
"""

#%%
# import packages

import pandas as pd
import numpy as np
import os

# Import user defined modules
code_path = 'C:\\Users\\skar\\repos\\EERE_decarb'

os.chdir(code_path)

from EIA_AEO_import import EIA_AEO
from Industrial_import import Industrial
from Agriculture_import import Agriculture
from Transportation_VISION_import import Transport_Vision
from EPA_GHGI_import import EPA_GHGI_import
from NREL_electricity_import import NREL_elec
from GREET_EF_import import GREET_EF
from unit_conversions import model_units   

#%%


#%%
# Analysis parameters

fetch_data = False # True for fetching data, False for loading pre-compiled data
save_interim_files = True

# Please 
#data_path_prefix = 'C:\\Users\\skar\\Box\\EERE SA Decarbonization\\1. Tool\\EERE Tool\\Data'
data_path_prefix = 'C:\\Users\\skar\\Box\\EERE SA Decarbonization\\1. Tool\EERE Tool\\Data\\Script_data_model'

f_eia = 'EIA Dataset.csv'
f_NREL_elec_option = 'report - All Options EFS.xlsx'
f_ef = 'GREET_EF_EERE.csv'
f_corr_eia = 'corr_EIA_EERE.csv'
f_corr_ef_greet = 'corr_EF_GREET.csv'
f_corr_fuel_pool = 'corr_fuel_pool.csv'
f_corr_elec_gen = 'corr_elec_gen.csv'

EIA_AEO_case_option = ['Reference case']

T_and_D_loss = 0.06

#%%
# Create data class objects

# Unit conversion class object
ob_units = model_units(data_path_prefix)

# EIA data import
if fetch_data == False:
    eia_data = pd.read_csv(data_path_prefix + '\\' + f_eia)
    eia_data = eia_data.loc[eia_data['AEO Case'].isin(EIA_AEO_case_option)]
else:
    eia_ob = EIA_AEO(save_interim_files, data_path_prefix)
    eia_data = eia_ob.eia_multi_sector_import(sectors = ['Residential',
                                                         'Commercial',
                                                         'Electric Power'
                                                         ],
                                                  
                                                  aeo_cases = EIA_AEO_case_option                                               
                                                  )

# Industrial data import
ob_industry = Industrial(ob_units, data_path_prefix)

# Agricultural and LULUCF data import
ob_agriculture = Agriculture(data_path_prefix)

# Transportation (VISION) data import
ob_transport = Transport_Vision(data_path_prefix)

# EPA GHGI data import
ob_EPA_GHGI = EPA_GHGI_import(ob_units, data_path_prefix)
ob_EPA_GHGI.remove_combustion_other_em() # removing 'combustion' and 'other' category emissions
if save_interim_files:
    ob_EPA_GHGI.df_ghgi.to_excel(data_path_prefix + '//' + 'interim_ob_EPA_GHGI.xlsx')

# NREL Electricity generation data import
ob_elec = NREL_elec(f_NREL_elec_option, data_path_prefix)

# GREET emission factor load
ob_ef = GREET_EF(f_ef, data_path_prefix)

# Data tables for correspondence across data sets

corr_EIA_EERE = pd.read_csv(data_path_prefix + '\\' + f_corr_eia, header = 3)
corr_EF_GREET = pd.read_csv(data_path_prefix + '\\' + f_corr_ef_greet, header = 3)
corr_fuel_pool = pd.read_csv(data_path_prefix + '\\' + f_corr_fuel_pool, header = 3)
corr_elec_gen = pd.read_csv(data_path_prefix + '\\' + f_corr_elec_gen, header = 3)

#%%

#%%
# Merge EIA and EPA's correspondence matrix
activity = pd.merge(eia_data, corr_EIA_EERE, how='right', left_on=['Sector', 'Subsector'], right_on=['EIA: Sector', 'EIA: Subsector']).dropna().reset_index()
activity.rename(columns = {'Sector_y' : 'Sector',
                           'Subsector_y' : 'Subsector', 
                           'End use' : 'End Use Application',
                           'Energy Carrier' : 'Activity', 
                           'Date' : 'Year',                            
                           'Series Id' : 'EIA Series ID'}, inplace = True)
activity = activity [['AEO Case', 'Sector', 'Subsector', 'EIA: End Use Application', 'Activity', 'Activity Type', 'Activity Basis', 
                      'Year', 'Unit', 'Value']]

# unit conversion
activity['unit_to'] = [ob_units.select_units(x) for x in activity['Unit'] ]
activity['unit_conv'] = activity['unit_to'] + '_per_' + activity['Unit'] 
activity['Value'] = np.where(
     [x in ob_units.dict_units for x in activity['unit_conv'] ],
     activity['Value'] * activity['unit_conv'].map(ob_units.dict_units),
     activity['Value'] )
activity.drop(['unit_conv', 'Unit'], axis = 1, inplace = True)
activity.rename(columns = {'unit_to' : 'Unit'}, inplace = True)

# Merge fuel pool
activity = pd.merge(activity, corr_fuel_pool, how='left', left_on=['Activity'],\
                    right_on=['Energy Carrier']).dropna().reset_index(drop=True)

# Extract electricity generation data from activity data frame
elec_gen = activity.loc[(activity['Sector'] == 'Electric Power') ].dropna().\
   reset_index(drop=True)

# Merge Electricity generation data with 'Electricity generation types' tags
elec_gen = pd.merge(elec_gen, corr_elec_gen, how='left', left_on=['Sector', 'Activity', 'Activity Type'],
                    right_on=['Sector', 'Activity', 'Activity Type']).\
    drop(['Index'], axis=1).reset_index(drop=True)
    

# Aggregrate electricity generation data by fuel type and by year
#elec_gen_agg =  elec_gen.groupby(['Year', 'Generation Type', 'Unit'])['Value'].sum().reset_index()

# Map with correlation matrix to GREET pathway names
temp_corr_EF_GREET = corr_EF_GREET[['Activity', 'Activity Type', 'GREET Pathway']].drop_duplicates()
ob_ef.ef = pd.merge(ob_ef.ef, temp_corr_EF_GREET, how='left',on='GREET Pathway')

# Filter combustion data for electricity generation 
ob_ef.ef_electric = ob_ef.ef.loc[ob_ef.ef['Activity Type'].isin(elec_gen['Activity Type'].unique())].drop_duplicates()
ob_ef.ef_electric = ob_ef.ef_electric.loc[ob_ef.ef['Scope'].isin(['Electricity, Combustion'])]

ob_ef.ef_electric.rename(columns = {'Unit (Numerator)' : 'EF_Unit (Numerator)',
                                    'Unit (Denominator)' : 'EF_Unit (Denominator)'}, inplace = True)

# Merge emission factors for fuel-feedstock combustion so used for electricity generation with net electricity generation
electric_ef_gen = pd.merge(ob_ef.ef_electric[['Flow Name', 'Formula', 'EF_Unit (Numerator)', 
                            'EF_Unit (Denominator)', 'Case', 'Scope', 'Year', 
                            'BAU', 'Elec0', 'Activity', 'Activity Type']], 
         elec_gen[['AEO Case', 'EIA: End Use Application', 'Sector', 'Subsector', 'Activity', 
                   'Activity Type', 'Activity Basis', 'Year', 'Unit', 'Value', 
                   'Energy Carrier', 'Fuel Pool', 'Generation Type', 'Energy Type']],
             how='left',
             on=['Activity', 'Activity Type', 'Year'])

# Calculate net emission by GHG species, from electricity generation    
electric_ef_gen['Total Emissions'] = electric_ef_gen['BAU'] * electric_ef_gen['Value'] 

if save_interim_files == True:
    electric_ef_gen.to_excel(data_path_prefix + '\\' + 'interim_electric_ef_gen.xlsx')

# Add additional columns, rename columns, re-arrange columns
electric_ef_gen = electric_ef_gen.rename(columns={
                                                  'BAU' : 'EF_withElec',
                                                  'Elec0' : 'EF_Elec0',
                                                  'EIA: End Use Application' : 'End Use Application',
                                                  'Value' : 'Energy Estimate'
                                        })
electric_ef_gen = electric_ef_gen[['AEO Case', 'Sector', 'Subsector', 'End Use Application', 
                          'Activity', 'Activity Type', 'Activity Basis', 'Fuel Pool', 'Case', 
                          'Year', 'Unit', 'Energy Estimate', 'Scope', 'Flow Name', 'Formula', 
                          'EF_Unit (Numerator)', 'EF_Unit (Denominator)', 
                          'EF_withElec', 'EF_Elec0', 'Total Emissions']]

# Aggrigration to calculate overall Electricity generation CI, combustion portion    
electric_ef_gen_agg = electric_ef_gen.groupby(['Year', 'Activity Type', 'Flow Name', \
                                               'Formula', 'Unit', 'EF_Unit (Numerator)']).agg({
                                                   'Value' : 'sum', 
                                                   'Total Emissions' : 'sum'})\
                                    .reset_index()\
                                    .rename(columns = {'Value' : 'Electricity Production',
                                                       'Unit' : 'Energy Unit',
                                                       'EF_Unit (Numerator)' : 'Emissions Unit'})
electric_ef_gen_agg['CI'] = electric_ef_gen_agg['Total Emissions'] / \
    ( electric_ef_gen_agg['Electricity Production'] * (1 - T_and_D_loss) )

if save_interim_files == True:
    electric_ef_gen_agg.to_csv(data_path_prefix + '\\' + 'interim_electric_ef_gen_agg_1.csv')
    

# Aggregrating to calculate the net energy generation per year, and corresponding GHG emissions
electric_ef_gen_agg = electric_ef_gen_agg.groupby(['Year', 'Flow Name', 'Formula', \
                                                   'Energy Unit', 'Emissions Unit']).agg({
                                                       'Electricity Production' : 'sum',
                                                       'Total Emissions' : 'sum'}) \
                                                           .reset_index()

""" Adding GHG emissions from incineration of waste from EPA's GHGI, 
Electrical Transmission and Distribution, and Other Process Uses of Carbonates.
Values from 2019, as constant to all the years.
"""
EPA_GHGI_addn_em = ob_EPA_GHGI.df_ghgi.loc[(ob_EPA_GHGI.df_ghgi['Source'].isin(
    ['Incineration of Waste', 
     'Electrical Transmission and Distribution', 
     'Other Process Uses of Carbonates'])) & 
   (ob_EPA_GHGI.df_ghgi['Year'] == 2019) ]

EPA_GHGI_addn_em = EPA_GHGI_addn_em.groupby(['Year', 'Source', \
                                                                   'Emissions Type',
                                                                   'Unit'])\
                                                         .agg({
                                                             'Value' : 'sum'
                                                             }).reset_index()
# unit conversion
EPA_GHGI_addn_em['unit_to'] = electric_ef_gen_agg['Emissions Unit'].unique()[0]
EPA_GHGI_addn_em['unit_conv'] = EPA_GHGI_addn_em['unit_to'] + '_per_' + EPA_GHGI_addn_em['Unit'] 
EPA_GHGI_addn_em['Value'] = np.where(
     [x in ob_units.dict_units for x in EPA_GHGI_addn_em['unit_conv'] ],
     EPA_GHGI_addn_em['Value'] * EPA_GHGI_addn_em['unit_conv'].map(ob_units.dict_units),
     EPA_GHGI_addn_em['Value'] )
EPA_GHGI_addn_em.drop(['unit_conv', 'Unit'], axis = 1, inplace = True)
EPA_GHGI_addn_em.rename(columns = {'unit_to' : 'Unit'}, inplace = True)

# Merge and add to electricity emissions df 
electric_ef_gen_agg = pd.merge(electric_ef_gen_agg, EPA_GHGI_addn_em[['Emissions Type', 'Value']], 
                               how='left', left_on='Formula', right_on='Emissions Type')
electric_ef_gen_agg['Total Emissions'] = electric_ef_gen_agg['Total Emissions'] + electric_ef_gen_agg['Value']
electric_ef_gen_agg.drop(['Value'], axis=1, inplace=True) # at this stage, the total emissions represent emissions including incineration of waste.

# Recalculate the Electricity generation, combustion based CI
electric_ef_gen_agg['CI'] = electric_ef_gen_agg['Total Emissions'] / \
    ( electric_ef_gen_agg['Electricity Production'] * (1 - T_and_D_loss) )
    
if save_interim_files == True:
    electric_ef_gen_agg.to_csv(data_path_prefix + '\\' + 'interim_electric_ef_gen_agg_2.csv')


# BAU scenario dev for non-electricity generation sectors and non-electric activities
activity_non_elec = activity.loc [~ (activity['Sector'] == 'Electric Power')]
activity_non_elec = activity_non_elec.loc [~ (activity_non_elec['Activity'] == 'Electricity')]

# Filter combustion data for electricity generation 
ob_ef.ef_non_electric = ob_ef.ef.loc[ob_ef.ef['Activity'].isin(activity_non_elec['Activity'].unique())].drop_duplicates()
ob_ef.ef_non_electric.rename(columns = {'Unit (Numerator)' : 'EF_Unit (Numerator)',
                                    'Unit (Denominator)' : 'EF_Unit (Denominator)'}, inplace = True)

# Merge emission factors for non-electric generation activites
non_electric_ef_activity = pd.merge(ob_ef.ef_non_electric[['Flow Name', 'Formula', 'EF_Unit (Numerator)', 
                            'EF_Unit (Denominator)', 'Case', 'Scope', 'Year', 
                                'BAU', 'Elec0', 'Activity']], 
         activity_non_elec[['AEO Case', 'Sector', 'Subsector', 'EIA: End Use Application',
                            'Activity', 'Activity Basis', 'Year', 'Unit', 
                            'Value', 'Energy Carrier', 'Fuel Pool']],
             how='left',
             on=['Activity', 'Year'])

# calculate total emissions
non_electric_ef_activity['Total Emissions'] = non_electric_ef_activity['BAU'] * non_electric_ef_activity['Value']
#non_electric_ef_activity.dropna(axis=1, how='all', inplace=True)

# Add additional columns, rename columns, re-arrange columns
"""
# targetted columns as per EERE tool's Env Matrix:
non_electric_ef_activity[['Activity', 'Activity Type', 'Activity Basis', 'Case', 
                          'Year', 'Unit', 'Value', 'Scope', 'Flow Names', 'Formula', 
                          'EF_Unit (Numerator)', 'EF_Unit (Denominator)', 
                          'EF_withElec', 'EF_Elec0', 'Total Emissions', 'LCIA Method', 'Metric', 
                          'Impact Factor', 'Metric Unit', 'LCIA Estimate', 
                          'Emission', 'Emissions Allocated to Sector', 
                          'Mitigation Measure']]
"""
non_electric_ef_activity[['Activity Type']] = '-'
non_electric_ef_activity = non_electric_ef_activity.rename(columns={
                                                            'BAU' : 'EF_withElec',
                                                            'Elec0' : 'EF_Elec0',
                                                            'EIA: End Use Application' : 'End Use Application',
                                                            'Value' : 'Energy Estimate'
                                                          })
non_electric_ef_activity = non_electric_ef_activity[['AEO Case', 'Sector', 'Subsector', 'End Use Application', 
                          'Activity', 'Activity Type', 'Activity Basis', 'Fuel Pool', 'Case', 
                          'Year', 'Unit', 'Energy Estimate', 'Scope', 'Flow Name', 'Formula', 
                          'EF_Unit (Numerator)', 'EF_Unit (Denominator)', 
                          'EF_withElec', 'EF_Elec0', 'Total Emissions']]
 
if save_interim_files == True:
    non_electric_ef_activity.to_excel(data_path_prefix + '\\' + 'interim_non_electric_ef_activity.xlsx')   
    

# Generate the Environmental Matrix
activity_BAU = pd.concat ([electric_ef_gen, non_electric_ef_activity], axis=0).reset_index(drop=True)

# Merge with EPA data
# env_mx = pd.merge(ob_EPA_GHGI.df_ghgi, activity, how='right', left_on=['Year', 'Sector', 'Subsector'], right_on=['EIA: Sector', 'EIA: Subsector']).dropna().reset_index()

if save_interim_files == True:
    activity.to_csv(data_path_prefix + '\\' + 'interim_activity.csv')





#%%
