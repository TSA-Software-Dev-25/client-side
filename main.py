import GPUtil
import json
import asyncio
import websockets
import subprocess
import base64
import os
import logging

#TODO: test docker at home
#TODO: pull home and set up logging

gpuMaxLoad = 0.5 # 50% load; should later be user defined
fileResultPath = 'file_result.json' # constant path for file result
url = 'ws://localhost:8080/connect-gpu' # websocket URL (currently placeholder)
token = 123456

# func for sending GPU info every 30 minutes
# calls getGPUs() 
# returns None
async def send(websocket):
        while True:
            payload = await getPayload(0)
            if payload is not None:
                try:
                    await websocket.send(json.dumps(payload))
                except Exception as err:
                    print(err)
            await asyncio.sleep(15)

# func for getting GPU info
# returns list of dicts with GPU info
# returns none if GPU load or memory exceeds max
async def getGPUs(): #TODO check if gputil can gather gpu temp if not then dont bother
    gpus = GPUtil.getGPUs() 
    gpuMemory = 0
    if gpus is not None:
        for gpu in gpus: # will parse through all data for every GPU in system 
            if gpu.load < gpuMaxLoad: # check if over user defined limit
                gpuMemory += gpu.memoryFree # assigns values for load and memory as floats
    return gpuMemory

#func for constructing payload
#returns dict with payload
async def getPayload(message):
    gpuInfo = await getGPUs()
    if gpuInfo is not None:
        payload = {
            "token": token,
            "memory": gpuInfo,
            "output": message
        }
        return payload
    else:
        return None

# func for listening to websocket
# calls messageHandler
async def listen(websocket):
    while True:
        try: 
            message = await websocket.recv()
            print(f'got message: {message}')
            data = json.loads(message)
            await messageHandler(data, websocket)
        except websockets.exceptions.ConnectionClosedOK:
            asyncio.run(main())
        except Exception as err:
            print("Error receiving ws: ", err)

# func parsing through message content
# should only look for JSON data with command "run-file"
#calls runFile() and sendOutput
# returns None
async def messageHandler(data, websocket):
    try:
        if data.get("command") == "run-file":
            if "file_name" in data and "file_content" in data: # required headers in JSON data that are constructed when json is sent
                path = data["file_name"]
                forwardingToken = data["token"]
                fileContent = base64.b64decode(data["file_content"]) # .py file transfers as base64 encoded string from frontend to backend to frontend
                with open(path, 'wb') as file:
                    file.write(fileContent)
                result = await runFile(path)
                print(result)
                await sendOutput(result, forwardingToken, websocket)
            else: 
                await sendOutput({"error": "JSON data is not structured correctly: please include file_name and file_content"}, forwardingToken, websocket)
    except Exception as err:
        print(err)

# func for running .py file given path
# returns dict with results of file
async def runFile():
    try:
        if path.endswith('.py'):
            print("now about to run file")
            execute = subprocess.run(["python", path], capture_output = True, text = True)
            result = {
            "stdout": execute.stdout, # stdout is the output of the file i.e "Hello, World!"
            "stderr": execute.stderr, # stderr is the error output of the file i.e "SyntaxError: invalid syntax"
            "returncode": execute.returncode, # returncode is the return code of the file i.e 0 or 1 
        }
            # os.remove(path) # remove file 
            return result
        else:
            return {"error": "unsupported file type: please use .py files"}
    except Exception as err:
        return {"error": str(err)} # return error as dict to parse as JSON
    
# func for sending file output data 
# returns None
async def sendOutput(sendData, forwardingToken, websocket):
    try:
        payload =  await getPayload(sendData)
        print(payload)
        payload["forwarding_token"] = forwardingToken
        print(payload)
        await websocket.send(json.dumps(payload))
        print("sent")
    except Exception as err:
        print(err)

# main function for running all functions
# calls sendGPU() and listen() at once
# enables program to send GPU continuously and listen to websocket
# returns None
async def main():
    try: 
        async with websockets.connect(url) as websocket:
            await asyncio.gather(send(websocket), listen(websocket))
    except Exception as err:
        print("Websocket error: %s" % err)
         
if __name__ == "__main__":
    logging.getLOgger(__name__)
    logging.basicConfig(filename='logs/logs.log', level=logging.INFO)
    asyncio.run(main())
    
