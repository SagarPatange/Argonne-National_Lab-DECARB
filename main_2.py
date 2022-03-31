# -*- coding: utf-8 -*-
"""
Created on Mon Jan 10 20:08:36 2022

@author: skar
"""

#%%
# Analysis parameters

# Update the _prefix paths based on your local Box folder location

code_path_prefix = 'C:\\Users\\skar\\repos\\EERE_decarb' # psth to the Github local repository

input_path_prefix = 'C:\\Users\\skar\\Box\\EERE SA Decarbonization\\1. Tool\\EERE Tool\\Data\\Script_data_model\\1_input_files'
interim_path_prefix = 'C:\\Users\\skar\\Box\\EERE SA Decarbonization\\1. Tool\\EERE Tool\\Data\\Script_data_model\\2_intermediate_files'
output_path_prefix = 'C:\\Users\\skar\\Box\\EERE SA Decarbonization\\1. Tool\\EERE Tool\\Data\\Script_data_model\\3_output_files'

# Declaring paths for data loading
input_path_EIA = input_path_prefix + '\\EIA'
input_path_EPA = input_path_prefix + '\\EPA_GHGI'
input_path_corr = input_path_prefix + '\\correspondence_files'
input_path_aggriculture = input_path_prefix + '\\Agriculture'
input_path_industrial = input_path_prefix + '\\Industrial'
input_path_electricity = input_path_prefix + '\\Electricity'
input_path_GREET = input_path_prefix + '\\GREET'
input_path_units = input_path_prefix + '\\Units'
input_path_transport = input_path_prefix + '\\Transportation'

# LCIA factors
f_lcia = 'gwp factors.xlsx'
f_lcia_sheet = 'Tidy'

# Declaring correlation filenames
f_eia = 'EIA Dataset.csv'
f_NREL_elec_option = 'report - All Options EFS.xlsx'
f_corr_ef_greet = 'corr_EF_GREET.xlsx'

sheet_corr_ef_greet = 'corr_EF_GREET'

# Model data pull and intermediate file saving options
EIA_AEO_fetch_data = False # True for fetching EIA AEO data, False for loading pre-compiled data
EIA_AEO_save_to_file = True # True for saving fetched data and saving it to file
save_interim_files = True

# GWP assumptions
# Note: Use AR4 100-Yr GWP Factors, so that results can be compared with EIA's GHGI.
LCIA_Method = 'AR4' # QA can use AR4, but model should be based on AR5
lcia_timeframe = 100

# EIA AEO data case
EIA_AEO_case_option = ['Reference case']

# T&D assumption, constant or calculated
T_and_D_loss_constant = True
# T_and_D_loss = 0.06

# parameter to print out additional information when code is running
verbose = True

#%%


#%%

# import packages
import pandas as pd
import numpy as np
import os
from datetime import datetime

# Import user defined modules
os.chdir(code_path_prefix)

from EIA_AEO_import import EIA_AEO
from Industrial_import import Industrial
from Agriculture_import import Agriculture
from Transportation_VISION_import import Transport_Vision
from EPA_GHGI_import import EPA_GHGI_import
from NREL_electricity_import import NREL_elec
from GREET_EF_import import GREET_EF
from unit_conversions import model_units   

#%%

init_time = datetime.now()

# Create data class objects

# Unit conversion class object
ob_units = model_units(input_path_units, input_path_GREET, input_path_corr)

# EIA data import and processing
ob_eia = EIA_AEO(input_path_EIA, input_path_corr)
ob_eia.EERE_data_flow_EIA_AEO(ob_units, EIA_AEO_fetch_data, EIA_AEO_save_to_file, verbose)

ob_EPA_GHGI = EPA_GHGI_import(ob_units, input_path_EPA, input_path_corr )

ob_EPA_GHGI.remove_combustion_other_em() # removing 'combustion' and 'other' category emissions

if save_interim_files:
    ob_EPA_GHGI.df_ghgi.to_excel(interim_path_prefix + '//' + 'interim_ob_EPA_GHGI.xlsx')

# NREL Electricity generation data import
ob_elec = NREL_elec(f_NREL_elec_option, input_path_electricity )

# GREET emission factor load
ob_ef = GREET_EF(input_path_GREET )
                      
# Data tables for correspondence across data sets
corr_EF_GREET = pd.read_excel(input_path_corr + '\\' + f_corr_ef_greet, sheet_name = sheet_corr_ef_greet, header = 3)

# Life Cycle Impact Assessment metrics table
lcia_data = pd.read_excel(input_path_EPA + '\\' + f_lcia, sheet_name = f_lcia_sheet)         
lcia_select = lcia_data.loc[ (lcia_data['LCIA Method'] == LCIA_Method) & (lcia_data['timeframe_years'] == lcia_timeframe) ]

#%%

#%%

# Hytdogen Economy: Track ng use as a feedstock for hydrogen in a separate df. Steam methane reform ef from thet data frame

print('Status: Constructing Electric generation activity and Emission Factors data frames ..')
 
"""
Steps for constructing electric generation activity and emissions:   
1. Pre-process emissions factor data
2. Aggregrate and calculate net generation and/or emissions in separate dfs/file. Consider T&D loss for electricity generation.
3. Merge two dfs and calculate direct-combustion electric generation CI
"""

# Map with correlation matrix to GREET pathway names
ob_ef.ef = pd.merge(corr_EF_GREET.loc[:, ~ corr_EF_GREET.columns.isin(['GREET Tab', 'GREET Version'])],
                    ob_ef.ef,
                    how='left',on=['GREET Pathway', 'Scope']).reset_index(drop=True)

ob_ef.ef.to_excel(interim_path_prefix + '\\' + 'temp_ef.xlsx')

# Filter combustion data for electricity generation 
ob_ef.ef_electric = ob_ef.ef.loc[ob_ef.ef['Scope'].isin(['Electricity, Combustion'])].copy()

ob_ef.ef_electric.rename(columns = {'Unit (Numerator)' : 'EF_Unit (Numerator)',
                                    'Unit (Denominator)' : 'EF_Unit (Denominator)'}, inplace = True)                

# Calculate aggregrated electricity generation and merge T&D loss
# Merge T&D loss data
electric_gen = ob_eia.EIA_data['energy_supply'].groupby(['Year', 'Sector', 'End Use', 'Energy carrier', 'Unit']).\
                                                agg({'Value' : 'sum'}).reset_index().\
                                                rename(columns = {'Value' : 'Electricity Production'})

electric_gen = pd.merge(electric_gen, ob_eia.TandD[['Year', 'loss_frac']], how='left', on='Year')
electric_gen['Electricity Production'] = electric_gen['Electricity Production'] * (1 - electric_gen['loss_frac'])
electric_gen.rename(columns={'End Use' : 'End Use Application'}, inplace=True)

if save_interim_files == True:
    electric_gen.to_excel(interim_path_prefix + '\\' + 'interim_electric_gen.xlsx')

# Merge emission factors for fuel-feedstock combustion used for electricity generation with net electricity generation
electric_gen_ef = pd.merge(ob_eia.EIA_data['energy_supply'][['AEO Case', 'End Use', 'Sector', 'Subsector', 'Energy carrier', 
                                     'Energy carrier type', 'Basis', 'Year', 'Unit', 'Value',
                                     'Fuel Pool', 'Generation Type', 'Case' ]],
                           ob_ef.ef_electric, 
             how='left',
             on=['Sector', 'Subsector', 'Energy carrier', 'Energy carrier type', 'Year', 'Case'])

# Calculate net emission by GHG species, from electricity generation    
electric_gen_ef['Total Emissions'] = electric_gen_ef['Reference case'] * electric_gen_ef['Value'] 

# Rename and re-arrange columns
electric_gen_ef = electric_gen_ef.rename(columns={
                                                  'Reference case' : 'EF_withElec',
                                                  'Elec0' : 'EF_Elec0',
                                                  'Unit' : 'Energy Unit',
                                                  'Value' : 'Electricity Production'
                                        })
electric_gen_ef = electric_gen_ef[['AEO Case', 'Case', 'GREET Pathway', 'Sector', 'Subsector', 'End Use Application', 
                          'Energy carrier', 'Energy carrier type', 'Basis', 'Fuel Pool', 
                          'Year', 'Energy Unit', 'Electricity Production', 'Scope', 'Flow Name', 'Formula', 
                          'EF_Unit (Numerator)', 'EF_Unit (Denominator)', 
                          'EF_withElec', 'Total Emissions']]

if save_interim_files == True:
    electric_gen_ef.to_excel(interim_path_prefix + '\\' + 'interim_electric_gen_emissions.xlsx')

# Aggregrate emissions
electric_gen_ef_agg = electric_gen_ef.groupby(['Year', 'Sector', 'End Use Application', 'Energy carrier', 'Flow Name', 'Formula', 'EF_Unit (Numerator)']).\
                                                agg({'Total Emissions' : 'sum'}).reset_index()   
                                                
if save_interim_files == True:
    electric_gen_ef_agg.to_excel(interim_path_prefix + '\\' + 'interim_electric_gen_emissions_agg.xlsx')
 
# merging the electricity production data with the total emissions data    
elec_gen_em_agg = pd.merge(electric_gen, electric_gen_ef_agg, how='left', on=['Year', 'Sector', 'End Use Application', 'Energy carrier']).drop(columns=['loss_frac']) 
elec_gen_em_agg.rename(columns={
    'Unit' : 'Energy Unit', 'EF_Unit (Numerator)' : 'Emissions Unit'}, inplace=True)
elec_gen_em_agg['CI'] = elec_gen_em_agg['Total Emissions'] / elec_gen_em_agg['Electricity Production']

if save_interim_files == True:
    elec_gen_em_agg.to_csv(interim_path_prefix + '\\' + 'interim_electric_agg_CI.csv')
                                                

""" Adding GHG emissions from incineration of waste from EPA's GHGI, 
Electrical Transmission and Distribution, and Other Process Uses of Carbonates.
Values from 2019, as constant to all the years.
"""


EPA_GHGI_maxyear = np.max(ob_EPA_GHGI.df_ghgi['Year'])
EPA_GHGI_addn_em = ob_EPA_GHGI.df_ghgi.loc[(ob_EPA_GHGI.df_ghgi['Source'].isin(
    ['Incineration of Waste', 
     'Electrical Transmission and Distribution', 
     'Other Process Uses of Carbonates'])) & 
   (ob_EPA_GHGI.df_ghgi['Year'] == EPA_GHGI_maxyear) ]
"""
EPA_GHGI_addn_em = EPA_GHGI_addn_em.\
    groupby(['Year', 'Source', 'Emissions Type', 'Unit']).\
        agg({'GHG Emissions' : 'sum'}).reset_index()
         
# unit conversion
EPA_GHGI_addn_em [['Unit', 'GHG Emissions']] = ob_units.unit_convert_df (
    EPA_GHGI_addn_em [['Unit', 'GHG Emissions']], Unit='Unit', Value='GHG Emissions', if_given_unit = True, 
    given_unit = electric_ef_gen_agg['Emissions Unit'].unique()[0]).copy()

# Merge and add to electricity emissions df 
electric_ef_gen_agg = pd.merge(electric_ef_gen_agg, EPA_GHGI_addn_em[['Emissions Type', 'GHG Emissions']], 
                               how='left', left_on='Formula', right_on='Emissions Type')
electric_ef_gen_agg['Total Emissions'] = electric_ef_gen_agg['Total Emissions'] + electric_ef_gen_agg['GHG Emissions']
electric_ef_gen_agg.drop(['GHG Emissions'], axis=1, inplace=True) # at this stage, the total emissions represent emissions including incineration of waste.

# Merge T&D loss data
electric_ef_gen_agg = pd.merge(electric_ef_gen_agg, ob_eia.TandD[['Year', 'loss_frac']], how='left', on='Year')

# Recalculate the Electricity generation, combustion based CI
electric_ef_gen_agg['CI'] = electric_ef_gen_agg['Total Emissions'] / \
    ( electric_ef_gen_agg['Electricity Production'] * (1 - electric_ef_gen_agg['loss_frac']) )
    
if save_interim_files == True:
    electric_ef_gen_agg.to_csv(interim_path_prefix + '\\' + 'interim_electric_ef_gen_agg_2.csv')
"""
# separate non-electric and electric activities --> merge to ef data frames and calculate total emissions
activity_elec = ob_eia.EIA_data['energy_demand'].loc[ob_eia.EIA_data['energy_demand']['Energy carrier'] == 'Electricity',:]
activity_non_elec = ob_eia.EIA_data['energy_demand'].loc[ob_eia.EIA_data['energy_demand']['Energy carrier'] != 'Electricity',:]

# Map direct combustion wrt energy carrier for non-electric. For electric, map aggregrate CIs that we calculated and then calculate the net emissions and GWPs
activity_elec = pd.merge(activity_elec, elec_gen_em_agg[['Year', 'Energy carrier', 'Energy Unit', 'Flow Name', 'Formula', 'Emissions Unit', 'CI']], 
         how='left', on=['Year', 'Energy carrier'])

activity_non_elec = pd.merge(activity_non_elec, ob_ef.ef, 
         how='left', on=['Case', 'Sector', 'Subsector', 'Energy carrier', 'Energy carrier type', 'End Use Application', 'Year'])
activity_non_elec.rename(columns={'Reference case' : 'CI',
                                  'Unit (Numerator)' : 'Emissions Unit'}, inplace=True)

activity_elec['Total Emissions'] = activity_elec['Value'] * activity_elec['CI']
activity_elec['Scope'] = 'Electricity, Combustion'

activity_non_elec['Total Emissions'] = activity_non_elec['Value'] * activity_non_elec['CI']
activity_non_elec['Scope'] = 'Direct, Combustion'

# Add additional columns, rename columns, re-arrange columns

activity_elec = activity_elec[['Data Source', 'AEO Case', 'Case', 'Sector', 'Subsector', 
                               'End Use Application', 'Scope', 'Energy carrier', 'Energy carrier type', 
                               'Basis', 'Fuel Pool', 'Year', 'Flow Name', 'Formula', 'Emissions Unit', 
                               'Unit', 'Value', 'CI', 'Total Emissions']]

activity_non_elec = activity_non_elec[['Data Source', 'AEO Case', 'Case', 'Sector', 'Subsector', 
                               'End Use Application', 'Scope', 'Energy carrier', 'Energy carrier type', 
                               'Basis', 'Fuel Pool', 'Year', 'Flow Name', 'Formula', 'Emissions Unit', 
                               'Unit', 'Value', 'CI', 'Total Emissions']]


# Exclude the non-energy flows in the env matrix


"""
print('Status: Constructing non-electric activity sectors as per EIA AEO data set ..')

# Reference case scenario dev for non-electricity generation sectors and non-electric activities
activity_non_elec = activity.copy()
activity_non_elec = activity_non_elec.loc [~ (activity_non_elec['Energy carrier'] == 'Electricity')]

# Filter combustion data for non electric
ob_ef.ef_non_electric = ob_ef.ef.loc[ob_ef.ef['Energy carrier'].isin(activity_non_elec['Energy carrier'].unique())].drop_duplicates()
ob_ef.ef_non_electric.rename(columns = {'Unit (Numerator)' : 'EF_Unit (Numerator)',
                                    'Unit (Denominator)' : 'EF_Unit (Denominator)'}, inplace = True)

# Merge emission factors for non-electric generation activites
non_electric_ef_activity = pd.merge(ob_ef.ef_non_electric[['Flow Name', 'Formula', 'EF_Unit (Numerator)', 
                            'EF_Unit (Denominator)', 'Case', 'Scope', 
                            'Sector', 'Subsector', 'End Use Application', 'Year', 
                                'Reference case', 'Elec0', 'Energy carrier', 'GREET Pathway']], 
         activity_non_elec[['AEO Case', 'Case', 'Sector', 'Subsector', 'End Use Application',
                            'Energy carrier', 'Basis', 'Year', 'Unit', 
                            'Value', 'Energy carrier type', 'Fuel Pool']],
             how='left',
             on=['Case', 'Sector', 'Subsector', 'End Use Application', 'Energy carrier', 'Year']).drop_duplicates()
non_electric_ef_activity.to_csv(interim_path_prefix + '\\' + 'non_electric_ef_activity_test.csv')   
# calculate total emissions
non_electric_ef_activity['Total Emissions'] = non_electric_ef_activity['reference case'] * non_electric_ef_activity['Value']
#non_electric_ef_activity.dropna(axis=1, how='all', inplace=True)

# Add additional columns, rename columns, re-arrange columns
#non_electric_ef_activity[['Activity Type']] = '-'
non_electric_ef_activity = non_electric_ef_activity.rename(columns={
                                                            'Reference case' : 'EF_withElec',
                                                            'Elec0' : 'EF_Elec0',
                                                            'Value' : 'Energy Estimate'
                                                          })
non_electric_ef_activity = non_electric_ef_activity[['AEO Case', 'Case', 'GREET Pathway', 'Sector', 'Subsector', 'End Use Application', 
                          'Energy carrier', 'Energy carrier type', 'Basis', 'Fuel Pool', 
                          'Year', 'Unit', 'Energy Estimate', 'Scope', 'Flow Name', 'Formula', 
                          'EF_Unit (Numerator)', 'EF_Unit (Denominator)', 
                          'EF_withElec', 'EF_Elec0', 'Total Emissions']]
 
if save_interim_files == True:
    non_electric_ef_activity.to_csv(interim_path_prefix + '\\' + 'interim_non_electric_ef_activity.csv')   
    
"""

# Arranging non-combustion emissions from EPA GHGI
print("Status: Constructing EPA GHGI emissions data frame as activity data frame ..")
# Filter latest year data from EPA GHGI
activity_non_combust = ob_EPA_GHGI.df_ghgi.loc[ob_EPA_GHGI.df_ghgi['Year'] == EPA_GHGI_maxyear].copy()

# preserve Category and Subcategory information in one column
activity_non_combust ['Category, Subcategory'] = activity_non_combust ['Category'].copy() + ', ' + activity_non_combust ['Subcategory'].copy()

# Select the needed columns
activity_non_combust = activity_non_combust[[
    'Economic Sector',
    'Source',
    'Segment',
    'Category, Subcategory',
    'Emissions Type',
    'Year',
    'Unit',
    'GHG Emissions'
    ]]

# Rename columns to match with activity df
activity_non_combust.rename(columns = {
    'Economic Sector' : 'Sector',
    'Source' : 'Subsector',
    'Segment' : 'Basis',
    'Category, Subcategory' : 'End Use Application',
    'Emissions Type' : 'Formula',
    'GHG Emissions' : 'Total Emissions'    ,
    'Unit' : 'Emissions Unit'
    }, inplace=True)

# Adding additional empty columns, to match with other activity df
activity_non_combust[['AEO Case', 
                      'Energy carrier',
                      'Energy carrier type',
                      'Fuel Pool',
                      'Flow Name',                      
                      'Unit',                      
                      'Value' ,
                      'CI'                              
                      ]] = '-'

# Defining values to specific columns
activity_non_combust['Case'] = 'Reference case'
activity_non_combust['Scope'] = 'Direct, Non-Combustion'
activity_non_combust['Data Source'] = 'EPA GHGI'

# Rearranging columns
activity_non_combust = activity_non_combust[['Data Source', 'AEO Case', 'Case', 'Sector', 'Subsector', 
                                             'End Use Application', 'Scope', 'Energy carrier', 'Energy carrier type', 
                                             'Basis', 'Fuel Pool', 'Year', 'Flow Name', 'Formula', 'Emissions Unit', 
                                             'Unit', 'Value', 'CI', 'Total Emissions']]
# Expand data set for all the years under study
EERE_yr_min = np.min(electric_gen_ef['Year']).astype(int)
EERE_yr_max = np.max(electric_gen_ef['Year']).astype(int)

activity_non_combust['Year'] = EERE_yr_min
activity_non_combust_exp = activity_non_combust.copy()
for yr in range(EERE_yr_min+1, EERE_yr_max+1):
    activity_non_combust['Year'] = yr
    activity_non_combust_exp = pd.concat ([activity_non_combust_exp, activity_non_combust], axis=0).reset_index(drop=True)

# Generate the Environmental Matrix
activity_BAU = pd.concat ([activity_non_combust_exp, activity_elec, activity_non_elec], axis=0).reset_index(drop=True)

# filter out incomplete rows if any 
activity_BAU = activity_BAU[activity_BAU['Total Emissions'] != ''].copy() 

# unit conversion
#activity_BAU [['EF_Unit (Numerator)', 'Total Emissions']] = \
#ob_units.unit_convert_df(activity_BAU [['Emissions Unit', 'Total Emissions']], Unit='Emissions Unit', Value='Total Emissions', if_given_category=True, unit_category='Emissions').copy()

# Calculate LCIA metric
activity_BAU = pd.merge(activity_BAU, lcia_select, how='left', left_on=['Formula'], right_on=['Emissions Type'] ).reset_index(drop=True)
activity_BAU['LCIA_estimate'] = activity_BAU['Total Emissions'] * activity_BAU['GWP']

#activity_BAU.drop_duplicates(inplace=True)

print("Status: Saving activity_reference case table to file ..")
if save_interim_files == True:
    activity_BAU.to_csv(interim_path_prefix + '\\' + 'interim_activity_reference_case.csv')

print( 'Elapsed time: ' + str(datetime.now() - init_time))



#%%
