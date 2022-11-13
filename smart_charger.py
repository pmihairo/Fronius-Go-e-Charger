import requests
import pprint
import time
import logging
import json
import paho.mqtt.client as mqtt_client
from datetime import datetime
from goecharger import GoeCharger

# smart-charger.py
# Integrates go-e Charger with Fronius. 
# relies on goecharger module https://pypi.org/project/goecharger/

# Reads total power produced from PV system from Fronius Inverter each 5 min
# Sets max power for go-e Charger each 5 min
# assumes fronius hostname resolves to fronius IP and charger IP address filled below. 
# assumes car charges on 2 phases. 
# If your car charges on more than 2 phases, you need to modify the power bands below (lines 165 to 206)

# tested with Fronius GEN24 and Go-e Charger hardware version 3, fw version 053.3

froniusHostname = "fronius"
chargerHostname = "192.168.68.128"
MQTTBroker = 'homeassistant'
sleepInterval = 180
chargerStatusFromMQTT = ""
chargerSmartFromMQTT = ""
MQTTBrokerPort = 1883
MQTTTopic = [("/charger/status",1),("/charger/smart",1)]
MQTTusername = 'mqtt'
MQTTpassword = 'pasw'



def connect_mqtt() -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    def on_message(client, userdata, message):
        data = message.payload
        receive = data.decode("utf-8")
        m_decode = json.loads(receive)
        topic = message.topic
        if topic == "/charger/status" and str(m_decode) == "{'state': 'OFF'}":
            chargerStatusFromMQTT = "OFF"
            print('charger status' + str(chargerStatusFromMQTT))

        if topic == "/charger/status" and str(m_decode) == "{'state': 'ON'}":
            chargerStatusFromMQTT = "ON"
            print('charger status' + str(chargerStatusFromMQTT))

        if topic == "/charger/smart" and str(m_decode) == "{'state': 'OFF'}":
            chargerSmartFromMQTT = "OFF"
            print('smart status' + str(chargerSmartFromMQTT))

        if topic == "/charger/status" and str(m_decode) == "{'state': 'ON'}":
            chargerSmartFromMQTT = "ON"
            print('smart status' + str(chargerSmartFromMQTT))


#        print("received message: " + str(m_decode) + " from topic: " + topic)

            
    client = mqtt_client.Client("homeserver")
    client.username_pw_set(MQTTusername, MQTTpassword)
    client.on_connect = on_connect
    client.connect(MQTTBroker, MQTTBrokerPort)
    client.loop_start()
    client.subscribe(MQTTTopic)
    client.on_message = on_message 
    time.sleep(3)
    client.loop_stop()


    return client 


def getData(froniusHostname, dataRequest):
    """
    All Request's come via this function.  It builds the url from args
    hostname and dataRequest.  It is advised to have a fronius hostname
    entry in /etc/hosts.  There is no authentication required, it is assumed
    you are on a local, private network.
    """
    try:
        url = "http://" + froniusHostname + dataRequest
        r = requests.get(url, timeout=60)
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
    return getData(froniusHostname, dataRq)


def GetMetersRealtimeData():
    """
    This request provides detailed information about the local energy grid from the meter.
    The values replied represent the current state. Because of data has multiple
    asynchrone origins it is a matter of facts that the sum of all
    powers (grid, load and generate) will differ from zero.
    """
    dataRq = '/solar_api/v1/GetMeterRealtimeData.cgi?Scope=System'
    return getData(froniusHostname, dataRq)


def PowerFlowRealtimeData(jPFRD):
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
    if car_status == 'charging finished, vehicle still connected':
        vehicle_connected = 'True'

    if vehicle_connected:
        print(str(now) + ' Vehicle Connected : '+str(vehicle_connected) + '. Starting work.')

    pp.pprint(chargerStatus)


# Just Initial Testing Code
def TestPowerFlowRealtimeData():
    pp = pprint.PrettyPrinter(indent=4)
    Site = PowerFlowRealtimeData(GetPowerFlowRealtimeData())
#    power_from_sun=int(Site[0]['P_PV'])
    pp.pprint(Site)
    time.sleep(3)



def main():
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    logging.basicConfig(filename="smart_charger.log", level=logging.INFO, format="%(asctime)s %(message)s")

    print(str(now) + ' Starting Up.')
    logging.info('Starting Up.')

    while True:
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            charger = GoeCharger(chargerHostname)
            chargerStatus = dict()
            result = dict()
            chargerStatus = charger.requestStatus()            

            currentCurrent = int(chargerStatus['charger_max_current'])
            print(str(now) + ' Charger max current: '+str(currentCurrent) + 'A.')
            logging.info('Charger max current is: '+str(currentCurrent) + 'A.')
            car_status = chargerStatus['car_status']
            
            vehicle_connected = 'False'
            if car_status == 'charging finished, vehicle still connected':
                vehicle_connected = 'True'
            
            if car_status == 'charging':
                vehicle_connected = 'True'

            vehicle_charging = 'False'
            if car_status == 'charging':
                vehicle_charging = 'True'
            
            if vehicle_connected == 'True':
                print(str(now) + ' Vehicle Connected.')
                logging.info('Vehicle Connected.')
                if vehicle_charging == 'True':
                    logging.info('Vehicle Charging.')

            Site = PowerFlowRealtimeData(GetPowerFlowRealtimeData())
            power_from_sun = int(Site[0]['P_PV'])
            print('Power from sun is ' + str(power_from_sun) + 'W')
            power_grid = int(Site[0]['P_Grid'])
            print('Power grid ' + str(power_grid) + 'W')

            logging.info('Power from sun is now: ' + str(power_from_sun) + 'W')
            logging.info('Power grid is now: ' + str(power_grid) + 'W')

            if power_from_sun <= 3000:
                if vehicle_charging == 'True':
                    print('Not enough power to charge. Stopping charging.')
                    logging.info('Not enough power to charge. Stopping charging.')
                    result = charger.setAllowCharging(0)
                    result = charger.setMaxCurrent(6)
                    currentCurrent = 6
                elif vehicle_charging == 'False':
                    print('Vehicle not charging, nothing to do.')
                    logging.info('Vehicle not charging, nothing to do.')

            if power_from_sun > 3000 and power_from_sun <= 3500:
                if currentCurrent != 6:
                    print('Setting charger to 6A')
                    logging.info('Setting charger to 6A')
                    currentCurrent = 6
                    result = charger.setMaxCurrent(6)

                if vehicle_charging == 'False':
                    print('Starting Charging')
                    logging.info('Starting Charging')
                    result = charger.setAllowCharging(1)

            if power_from_sun > 3500 and power_from_sun <= 4000:
                if currentCurrent != 7:
                    print('Setting charger to 7A')
                    logging.info('Setting charger to 7A')
                    currentCurrent = 7
                    result = charger.setMaxCurrent(7)

                if vehicle_charging == 'False':
                    print('Starting Charging')
                    logging.info('Starting Charging')
                    result = charger.setAllowCharging(1)

            if power_from_sun > 4000 and power_from_sun <= 4500:
                if currentCurrent != 8:
                    print('Setting charger to 8A')
                    logging.info('Setting charger to 8A')
                    currentCurrent = 8
                    result = charger.setMaxCurrent(8)

                if vehicle_charging == 'False':
                    print('Starting Charging')
                    logging.info('Starting Charging')
                    result = charger.setAllowCharging(1)

            if power_from_sun > 4500 and power_from_sun <= 5100:
                if currentCurrent != 9:
                    print('Setting charger to 9A')
                    logging.info('Setting charger to 9A')
                    currentCurrent = 9
                    result = charger.setMaxCurrent(9)

                if vehicle_charging == 'False':
                    print('Starting Charging')
                    logging.info('Starting Charging')
                    result = charger.setAllowCharging(1)

            if power_from_sun > 5100 and power_from_sun <= 5600:
                if currentCurrent != 10:
                    print('Setting charger to 10A')
                    logging.info('Setting charger to 10A')
                    currentCurrent = 10
                    result = charger.setMaxCurrent(10)

                if vehicle_charging == 'False':
                    print('Starting Charging')
                    logging.info('Starting Charging')
                    result = charger.setAllowCharging(1)

            if power_from_sun > 5600 and power_from_sun <= 6100:
                if currentCurrent != 11:
                    print('Setting charger to 11A')
                    logging.info('Setting charger to 11A')
                    currentCurrent = 11
                    result = charger.setMaxCurrent(11)

                if vehicle_charging == 'False':
                    print('Starting Charging')
                    logging.info('Starting Charging')
                    result = charger.setAllowCharging(1)

            if power_from_sun > 6100 and power_from_sun <= 6500:
                if currentCurrent != 12:
                    print('Setting charger to 12A')
                    logging.info('Setting charger to 12A')
                    currentCurrent = 12
                    result = charger.setMaxCurrent(12)

                if vehicle_charging == 'False':
                    print('Starting Charging')
                    logging.info('Starting Charging')
                    result = charger.setAllowCharging(1)

            if power_from_sun > 6500:
                if currentCurrent != 13:
                    print('Setting charger to 13A')
                    logging.info('Setting charger to 13A')
                    currentCurrent = 13
                    result = charger.setMaxCurrent(13)

                if vehicle_charging == 'False':
                    print('Starting Charging')
                    logging.info('Starting Charging')
                    result = charger.setAllowCharging(1)

            time.sleep(sleepInterval)

            if vehicle_connected == 'False':
                print(str(now) + ' Vehicle Connected : ' + str(vehicle_connected) + '. Nothing to do.')
                logging.info('Vehicle Connected : ' + str(vehicle_connected) + '. Nothing to do.')
                time.sleep(sleepInterval)
        except:
            logging.error('exception. sleeping 10 min.', exc_info=True)
            time.sleep(sleepInterval)


if __name__ == "__main__":
    client = connect_mqtt()
    main()
#    TestChargerStatus()
#    TestPowerFlowRealtimeData()
