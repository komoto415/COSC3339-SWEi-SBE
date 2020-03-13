import http.server
from http.server import BaseHTTPRequestHandler
import json
import mysql.connector as sqldb
import requests
from dispatch import Dispatch
from enums.servicetype import ServiceType
from enums.vehiclestatus import VechileStatus
from enums.dispatchstatus import DispatchStatus
from utils.vehicleutils import getRoute, getEta
from utils.serverutils import connectToSQLDB
from datetime import datetime
import time
from copy import deepcopy
import random


# TODO: ISOto and ISOfrom for transferring datetype in json between backends


# def connectToSQLDB():
#     return sqldb.connect(user = 'root', password = 'password', database = 'team22supply', port = 6022)


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    ver = '0.3.1'
    
    # How to convert the body from a string to a dictionary
    # use 'loads' to convert from byte/string to a dictionary!
    def getPOSTBody(self):
        length = int(self.headers['content-length'])
        body = self.rfile.read(length)
        return json.loads(body)
    
    def do_POST(self):
        path = self.path
        print(path)
        responseDict = {}
        dictionary = self.getPOSTBody()
        sqlConnection = connectToSQLDB()
    
        if '/vehicleRequest' in path:
            print(dictionary)
            # Query all vehicles whose status is 'Active' and are a part of the fleet whose service time is the
            # incoming order's service type
            vehicleEntries = ()
            data = (dictionary['serviceType'],)
            statement = '''SELECT * FROM vehicles, fleets
                        WHERE status = 1 and type = %s and
                        vehicles.fleetid = fleets.fleetid'''
            with sqlConnection.cursor as cursor:
                cursor.execute(statement, data)
                vehicleEntries = cursor.fetchall();
        
            print(vehicleEntries)
            vehicle = vehicleEntries[0]
        
            # Capture vehicle tuple into its separate variables
            vid, status, licensePlate, fleetId, make, model, vLat, vLon = vehicle
            # Seeing if the unpacking worked d:
            print(vehicle)
            print(vid)
            print(status)
            print(licensePlate)
            print(fleetId)
            print(make)
            print(model)
            print(vLon)
            print(vLat)
        
            vehicleDict = {
                'vid': vid,
                'licensePlate': licensePlate,
                'make': make,
                'model': model,
                'curLocation': {
                    'lat': vLat,
                    'lon': vLon
                    },
                }
        
            print(vehicleDict)
            # Deep copy the dictionary because we'll need to mutate what's in here a bit. Also separates this from
            # the already existing containers floating around
            dispatchDict = deepcopy(dictionary)
            dispatchDict['vid'] = vid
        
            # Turn a destination dictionary into a tupled pair
            dispatchDict['destination'] = (dispatchDict['destination']['lat'], dispatchDict['destination']['lpm'])
        
            # Format for Dispatch class
            dispatchDict['loc_f'] = dispatchDict['destination']
            dispatchDict['loc_0'] = (vLat, vLon)
            print(dispatchDict)

            dispatch = Dispatch(**dispatchDict)
            print(dispatch)

            print('Time: ', dispatch.timeCreated)
            # print(type(dispatch.timeCreated))

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            print(dispatch.vid)

            data = (
                dispatch.vid, dispatch.cid, dispatch.oid,
                dispatch.loc_0[1], dispatch.loc_0[0], dispatch.loc_f[1], dispatch.loc_f[0],
                timestamp, dispatch.status.value, dispatch.sType.value
                )
            statement = '''INSERT INTO dispatch
                        (vid, custid, orderid, start_lat, start_lon, end_lat, end_lon, start_time, status, type)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
            with sqlConnection.cursor() as cursor:
                cursor.execute(statement, data)
                sqlConnection.commit()

            eta = getEta()[1]
            print(eta)
        
            vehicleDict['ETA'] = eta
        
            status = 200
            responseDict = vehicleDict
        
        elif '/addVehicle' in path:
            print(dictionary)
            fleetToAddTo = dictionary.pop('fleetNum')
            print(dictionary)

            data = []
            for key, value in dictionary.items():
                print(key)
                entry = (1, value['LicensePlate'], int(fleetToAddTo), value['Make'], value['Model'], 12.12, 34.34)
                print(entry)
                data.append(entry)
            print(data)
            statement = '''INSERT INTO vehicles
                        (status, licenseplate, fleetid, make, model, current_lat, current_lon)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)'''
            with sqlConnection.cursor() as cursor:
                cursor.executemany(statement, data)
                sqlConnection.commit()

            status = 200

        elif '/removeVehicle' in path:
            print(dictionary)
    
            statement = 'DELETE FROM vehicles (vid) WHERE vid = %s'
            data = ((x,) for x in dictionary['deleteMe'])
            with sqlConnection.cursor() as cursor:
                cursor.executemany(statement, data)
                sqlConnection.commit()
    
            status = 200

        elif '/addFleet' in path:
            print(dictionary)
            dictionary = {
                'newFleet1': {
                    'region': 'Austin',
                    'serviceType': 'Dry Cleaning',
                    'fmid': 123
                    }
                }
            data = []
            for key, value in dictionary.items():
                print(key)
                entry = (value['region'], value['serviceType'], value['fmid'])
                print(entry)
                data.append(entry)
            print(data)
            statement = 'INSERT INTO fleets (region, type, fmid) VALUES (%s, %s, %s)'
            with sqlConnection.cursor() as cursor:
                cursor.execute(statement, data)
                sqlConnection.commit()

            status = 200

        else:
            status = 404
    
        sqlConnection.close()
        self.send_response(status)
        self.end_headers()
        res = json.dumps(responseDict)
        bytesStr = res.encode('utf-8')
        self.wfile.write(bytesStr)
    
    def do_GET(self):
        vehicleList = self.getVehicles()
        path = self.path
        params = path.split('/')[-1].strip('?')
        sqlConnection = connectToSQLDB()
        status = 200
        responseDict = {}
        if '/vehicleRequest' in path:
            vid = ""
            statement = 'SELECT * FROM vehicles'
            if len(params) != 0:
                vid = int(params.split('=')[1])
                statement += ' WHERE vid = %s'
            with sqlConnection.cursor() as cursor:
                cursor.execute(statement, vid)
                responseDict = cursor.fetchall()

            status = 200

        elif '/etaRequest' in path:
            oid = int(params.split('=')[1])
            statement = 'SELECT * FROM dispatch WHERE oid = %s'
            with sqlConnection.cursor() as cursor:
                cursor.execute(statement, oid)
                responseDict = cursor.fetchall()

            status = 200

        elif '/getDispatch' in path:
            vid = int(params.split('=')[1])
            statement = 'SELECT * FROM dispatch WHERE vid = %s'
            dispatchTup = ()
            with sqlConnection.cursor() as cursor:
                cursor.execute(statement, vid)
                dispatchTup = cursor.fetchall()

            dispatchID = [list(x)[0] for x in dispatchTup]
            renderedCols = [list(x)[2:4] + list(x)[6:10] for x in dispatchTup]

            status = 200
            responseDict = dict(zip(dispatchID, renderedCols))
            # for key, value in zip(dispatchID, renderedCols):
            #     responseDict[f'dispatch{key}'] = {
            #         'orderID': value[1],
            #         'custID': value[0],
            #         'dest': (value[2], value[3]),
            #         'timeOrderPlaced': value[4],
            #         'status': value[5]
            #     }

        else:
            status = 404

        sqlConnection.close()
        self.send_response(status)
        self.end_headers()
        res = json.dumps(responseDict)
        bytesStr = res.encode('utf-8')
        self.wfile.write(bytesStr)


def main():
    port = 4022
    # Create an http server using the class and port you defined
    httpServer = http.server.HTTPServer(('', port), SimpleHTTPRequestHandler)
    print("Running on port", port)
    # this next call is blocking! So consult with Devops Coordinator for
    # instructions on how to run without blocking other commands frombeing
    # executed in your terminal!
    httpServer.serve_forever()


if __name__ == '__main__':
    main()
