# -*- coding: utf-8 -*-
"""
Created on Wed Jan 19 09:12:20 2022

@Project: EERE Decarbonization
@Authors: Saurajyoti Kar and George G. Zaimes
@Affiliation: Argonne National Laboratory
@Date: 01/19/2022

Summary: This python script loads Industrial activity based emissions data (2020 - 2050)
to a class and pre-processes it. Data sourced by Hoyoung Kwon

"""

#%%
#Import Python Libraries

import pandas as pd
import numpy as np
import os

# Import user defined modules
code_path = 'C:\\Users\\skar\\repos\\EERE_decarb'
os.chdir (code_path)

import unit_conversions as ut

#%%

class Industrial:
    
    """
    """
    
    def __init__ (self):
        
        # data loading
        self.path_data = 'C:\\Users\\skar\\Box\\saura_self\\Proj - EERE Decarbonization\\data'
        self.f_name = 'Industrial.xlsx'
        self.industrial = pd.read_excel(self.path_data + '\\' + self.f_name, header = 3)
               
        # unit, GJ to MMBtu
        self.industrial['unit_to'] = self.industrial['Unit']
        self.industrial.loc[self.industrial['unit_to'] == 'GJ', 'unit_to'] = 'MMBtu' 
    # extract the target unit to be converted to from a 'dictionary of energy units', rather than hard
    # coding the target unit. SImilar approach can be perforemd for mapping of categories.
    # Have a column in mitigation matrix where flows are referred by 'energy', 'emissions', etc.
        
        self.industrial['unit_conv'] = self.industrial['unit_to'] + '_per_' + self.industrial['Unit']
        self.industrial['Value'] = np.where(
             [x in ut.unit1_per_unit2 for x in self.industrial['unit_conv'] ],
             self.industrial['Value'] * self.industrial['unit_conv'].map(ut.unit1_per_unit2),
             self.industrial['Value'] )
        self.industrial.drop(['unit_conv', 'Unit'], axis = 1, inplace = True)
        self.industrial.rename(columns = {'unit_to' : 'Unit'}, inplace = True)
        
        # scaling values using adoption curve
        self.industrial['Value_scaled'] = self.industrial['Value'] * \
        [ self.adoption_curve(0, 100, 0.5, 2020, 2050, x, 1) for x in self.industrial['Year']]
        
        # add a separate column in mitigation, activity matrix 
            
    def adoption_curve (self,
                        min_val,
                        max_val,
                        k,
                        start_yr,
                        end_yr,
                        curr_yr,
                        a):
        x = curr_yr
        x_0 = int ( (start_yr + end_yr) /2 )
        val = min_val + (max_val - min_val) * pow ((1 / (1 + np.exp( -k * (x - x_0)))), a) 
        return val

# A variable option that can change the adaption curve parameters as input.
# The mitigation option should have different choices for the adoption curve parameters
# 

if __name__ == '__main__':
    ob1 = Industrial()
    
    print(ob1.industrial)