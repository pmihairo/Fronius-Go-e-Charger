import requests
import pprint
import time
import pandas as pd
import logging
from datetime import datetime
from goecharger import GoeCharger
from systemd import journal



# smart-charger.py
# Integrates go-e Charger with Fronius. 
# relies on goecharger module https://pypi.org/project/goecharger/

# Reads total power produced from PV system from Fronius Inverter each 5 min
# Sets max power for go-e Charger each 5 min
# assumes fronius hostname resolves to fronius IP and charger IP address filled below. 
# assumes car charges on 2 phases. 
# If your car charges on more than 2 phases, you need to modify the power bands below (lines 165 to 206)

# tested with Fronius GEN24 and Go-e Charger hardware version 3, fw version 053.3

#todo:
# refactor
# add 1 phase power support (may need to update goecharger module to set number of phases for charging.)


froniusHostname = "fronius"
chargerHostname = "192.168.68.128"
sleepInterval = 180


def getData(froniusHostname,dataRequest):
    """
    All Request's come via this function.  It builds the url from args
    hostname and dataRequest.  It is advised to have a fronius hostname
    entry in /etc/hosts.  There is no authentication required, it is assumed
    you are on a local, private network.
    """
    try:
        url = "http://" + froniusHostname + dataRequest
        r = requests.get(url,timeout=60)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        print("Request: {} failed ".format(url))
    except requests.exceptions.RequestException as e:
        print("Request failed with {}".format(e))

    exit()


def GetPowerFlowRealtimeData():
    """
    This request provides detailed information about the local energy grid.
    The values replied represent the current state. Because of data has multiple
    asynchrone origins it is a matter of facts that the sum of all
    powers (grid, load and generate) will differ from zero.
    """
    dataRq = '/solar_api/v1/GetPowerFlowRealtimeData.fcgi'
    return getData(froniusHostname,dataRq)

def GetMetersRealtimeData():
    """
    This request provides detailed information about the local energy grid from the meter.
    The values replied represent the current state. Because of data has multiple
    asynchrone origins it is a matter of facts that the sum of all
    powers (grid, load and generate) will differ from zero.
    """
    dataRq = '/solar_api/v1/GetMeterRealtimeData.cgi?Scope=System'
    return getData(froniusHostname,dataRq)



def PowerFlowRealtimeData(jPFRD):
# Collect the Inverter Data
# Does not include Optional Fields at this time
    Inverters = dict()
    Site = dict()
# There could be more than 1 inverter here -  Bitcoin Miners :)
    for i in jPFRD['Body']['Data']['Inverters']:
        Inverters['DeviceId'] = i
        Inverters['DT'] = jPFRD['Body']['Data']['Inverters'][i]['DT']
        Inverters['P'] = jPFRD['Body']['Data']['Inverters'][i]['P']

# Collect Site data (single row)
        Site['Timestamp'] = jPFRD['Head']['Timestamp']
        Site['Version'] = jPFRD['Body']['Data']['Version']
        Site['E_Day'] = jPFRD['Body']['Data']['Site']['E_Day']
        Site['E_Total'] = jPFRD['Body']['Data']['Site']['E_Total']
        Site['E_Year'] = jPFRD['Body']['Data']['Site']['E_Year']
        Site['Meter_Location'] = jPFRD['Body']['Data']['Site']['Meter_Location']
        Site['Mode'] = jPFRD['Body']['Data']['Site']['Mode']
        Site['P_Akku'] = jPFRD['Body']['Data']['Site']['P_Akku']
# TODO: Make Site(P_Akku) not 'None' 
        Site['P_Grid'] = jPFRD['Body']['Data']['Site']['P_Grid']
        Site['P_Load'] = jPFRD['Body']['Data']['Site']['P_Load']
        Site['P_PV'] = jPFRD['Body']['Data']['Site']['P_PV']
        Site['rel_Autonomy'] = jPFRD['Body']['Data']['Site']['rel_Autonomy']
        Site['rel_SelfConsumption'] = jPFRD['Body']['Data']['Site']['rel_SelfConsumption']
    return [Site, Inverters]



def GetChargerStatus():
    charger = GoeCharger(chargerHostname)
    pp = pprint.PrettyPrinter(indent=4)
    chargerStatus = dict()
    chargerStatus = charger.requestStatus()
    pp.pprint(chargerStatus)
    return chargerStatus

def TestChargerStatus():
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    pp = pprint.PrettyPrinter(indent=4)
    chargerStatus = GetChargerStatus()
    car_status = chargerStatus['car_status']
    vehicle_connected = 'False'
    if car_status == 'charging finished, vehicle still connected': vehicle_connected = 'True'
    if vehicle_connected:
        print(str(now) + ' Vehicle Connected : '+str(vehicle_connected) + '. Starting work.')
    pp.pprint(chargerStatus)


### Just Initial Testing Code
def TestPowerFlowRealtimeData():
    pp = pprint.PrettyPrinter(indent=4)
    Site = PowerFlowRealtimeData(GetPowerFlowRealtimeData())
    power_from_sun=int(Site[0]['P_PV'])
    pp.pprint(Site)
    time.sleep(3)



        
def main():
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    logging.basicConfig(filename="smart_charger.log", level=logging.INFO, format="%(asctime)s %(message)s")

#    print(str(now) + ' Starting Up.')
    logging.info('Starting Up.')

    while True:
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            charger = GoeCharger(chargerHostname)
            chargerStatus = dict()
            result = dict()
            chargerStatus = charger.requestStatus()            

            currentCurrent = int(chargerStatus['charger_max_current'])
#            print(str(now) + ' Charger max current: '+str(currentCurrent) + 'A.')
            logging.info ('Charger max current is: '+str(currentCurrent) + 'A.')
            car_status = chargerStatus['car_status']
            vehicle_connected = 'False'
            if car_status == 'charging finished, vehicle still connected': vehicle_connected = 'True'
            if car_status == 'charging': vehicle_connected = 'True'       

            vehicle_charging = 'False'
            if car_status == 'charging': vehicle_charging = 'True'       

            if vehicle_connected == 'True':
#                print(str(now) + ' Vehicle Connected.')
                logging.info('Vehicle Connected.')
#                journal.write('Vehicle Connected.')

            if vehicle_charging == 'True':
                logging.info('Vehicle Charging.')
#                journal.write('Vehicle Charging.')          
                
                Site = PowerFlowRealtimeData(GetPowerFlowRealtimeData())
                power_from_sun=int(Site[0]['P_PV'])
#                print('Power from sun is '+ str(power_from_sun) + 'W')
                logging.info ('Power from sun is now: '+ str(power_from_sun) + 'W')

                if power_from_sun <= 2800:
                    if vehicle_charging == 'True':
#                        print ('Should not charge now as power from sun is too low. Vehicle charging. Stopping charging.')
                        logging.info ('Should not charge now as power from sun is too low. Vehicle charging. Stopping charging.')
                        result = charger.setAllowCharging(0)   
                        result = charger.setMaxCurrent(6)
                        currentCurrent = 6
                    elif vehicle_charging == 'False':
#                        print ('Should not charge now as power from sun is too low. Vehicle not charging, nothing to do.')
                        logging.info('Should not charge now as power from sun is too low. Vehicle not charging, nothing to do.')

                if power_from_sun > 2800 and power_from_sun <= 3200:
                    if currentCurrent != 6:
#                        print ('Setting charger to 6A')
                        logging.info('Setting charger to 6A')
                        currentCurrent = 6
                        result = charger.setMaxCurrent(6)

                    if vehicle_charging == 'False':
#                        print ('Starting Charging')
                        logging.info('Starting Charging')
                        result = charger.setAllowCharging(1)

                if power_from_sun > 3200 and power_from_sun <= 3700:
                    if currentCurrent != 7:
#                        print ('Setting charger to 7A')
                        logging.info ('Setting charger to 7A')
                        currentCurrent = 7
                        result = charger.setMaxCurrent(7)

                    if vehicle_charging == 'False':
#                        print ('Starting Charging')
                        logging.info('Starting Charging')
                        result = charger.setAllowCharging(1)

                if power_from_sun > 3700 and power_from_sun <= 4100:
                    if currentCurrent != 8:
#                        print ('Setting charger to 8A')
                        logging.info ('Setting charger to 8A')
                        currentCurrent = 8
                        result = charger.setMaxCurrent(8)

                    if vehicle_charging == 'False':
#                        print ('Starting Charging')
                        logging.info('Starting Charging')
                        result = charger.setAllowCharging(1)

                if power_from_sun > 4100 and power_from_sun <= 4600:
                    if currentCurrent != 9:
#                        print ('Setting charger to 9A')
                        logging.info ('Setting charger to 9A')
                        currentCurrent = 9                    
                        result = charger.setMaxCurrent(9)

                    if vehicle_charging == 'False':
#                        print ('Starting Charging')
                        logging.info('Starting Charging')
                        result = charger.setAllowCharging(1)
  
                if power_from_sun > 4600:
                    if currentCurrent != 10:
#                        print ('Setting charger to 10A')
                        logging.info ('Setting charger to 10A')
                        currentCurrent = 10
                        result = charger.setMaxCurrent(10)

                    if vehicle_charging == 'False':
#                        print ('Starting Charging')
                        logging.info('Starting Charging')
                        result = charger.setAllowCharging(1)
                
                time.sleep(sleepInterval)
 
            if vehicle_connected == 'False':
#                print(str(now) + ' Vehicle Connected : '+str(vehicle_connected) + '. Nothing to do.')
                logging.info ('Vehicle Connected : ' + str(vehicle_connected) + '. Nothing to do.')
                time.sleep(sleepInterval)


        except:
            time.sleep(sleepInterval)
            print("exception. sleeping 1 min.")
            logging.error ('exception. sleeping 1 min.')


if __name__ == "__main__":
    main()
#    TestChargerStatus()
#    TestPowerFlowRealtimeData()


