import time 
import sqlite3 
import requests as req


conn2=sqlite3.connect('erp.db')
curs2=conn2.cursor()
from datetime import datetime



 
while(1):
         time.sleep(5) 
         print("********************SENDING PRODUCTION DATA****************************")
         try:
           curs2.execute("select * from production_status")
           idNo=curs2.fetchone()[2]
           print("Production Last value : " + str(idNo))
           curs2.execute("select * from production where id>(?) ",(idNo,))
           for row in curs2.fetchall():
                id=str(row[0])
                machineId=row[11]
                operatorName=row[1]
                jobId=row[2]
                shift=row[3]
                component=row[4]
                modelName=row[5]
                operation=row[6]
                cycleTime=row[7]
                inspectionStatus=row[8]
                status=row[9]
                timeStamp=datetime.strptime(row[10], '%Y/%m/%d %H:%M:%S') 
                try:
                   time.sleep(1)
                   data={
                            "ID" :id,
                           "MachineID":machineId,
                           "Operation":operation,
                           "OperatorName":operatorName,
                           "JobID":jobId,
                           "Model":modelName,
                           "Component":component,
                           "CycleTime":float(cycleTime),
                           "TimeStamp":timeStamp,
                           "Status":int(status),
                           "Shift":shift,
                           "InspectionStatus":inspectionStatus
                        }
                   response=req.post("http://10.130.10.6/BE/api/iiot/Production",timeout=2,data=data)
                   #response=req.get(url+"?machineId="+machineId+"&process="+process+"&timeStamp="+str(timeStamp),timeout=1)
                   if(response.status_code>=200 and response.status_code<=206):
                        curs2.execute("update production_status set value=(?) where status=(?)",(id,"test"))
                        print("{} entry updated..").format(id)
                        conn2.commit()
                   else:
                      print(response.status_code)        
                except Exception as e:
                     print(e)
                     break;

         except Exception as e:
            print(e)            


      