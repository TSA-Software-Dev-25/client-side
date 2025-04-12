import GPUtil
import json
import asyncio
import websockets
import subprocess
import base64
import os
import logging

#TODO: test docker at home

gpuMaxLoad = 0.5 # 50% load; should later be user defined
fileResultPath = 'file_result.json' # constant path for file result
url = 'ws://localhost:8080/exchange/connect' # websocket URL (currently placeholder)
token = 123456

# func for sending GPU info every 30 minutes
# calls getGPUs() 
# returns None
async def send(websocket):
        while True:
            logging.debug("gathering payload")
            payload = await getPayload(0)
            logging.debug(f"payload gathered: {payload}")
            if payload is not None:
                try:
                    logging.debug(f"sending payload to websocket - {websocket}")
                    await websocket.send(json.dumps(payload))
                    logging.debug(f"{payload} sent")
                    logging.info("Sent GPU information to server")
                except Exception as err:
                    logging.error(f"Error sending payload: {err}")
            await asyncio.sleep(15)

# func for getting GPU info
# returns list of dicts with GPU info
# returns none if GPU load or memory exceeds max
async def getGPUs(): #TODO check if gputil can gather gpu temp if not then dont bother
    gpus = GPUtil.getGPUs() 
    logging.debug(f"got gpus: {gpus}")
    gpuMemory = 0
    if gpus is not None:
        for gpu in gpus: # will parse through all data for every GPU in system 
            if gpu.load < gpuMaxLoad: # check if over user defined limit
                logging.debug(f"got gpu memory : {gpu.memoryFree}")
                gpuMemory += gpu.memoryFree # assigns values for load and memory as floats
    return gpuMemory

#func for constructing payload
#returns dict with payload
async def getPayload(message):
    logging.debug("getting gpu information")
    gpuInfo = await getGPUs()
    logging.debug(f"gpuInfo: {gpuInfo}")
    if gpuInfo is not None:
        payload = {
            "token": token,
            "memory": gpuInfo,
            "output": message
        }
        logging.debug(f"payload: {payload}")
        return payload
    else:
        logging.debug(f"gpuInfo is None: {gpuInfo}")
        return None

# func for listening to websocket
# calls messageHandler
async def listen(websocket):
    logging.debug("starting listen()")
    while True:
        try: 
            message = await websocket.recv()
            logging.debug(f'got message: {message}')
            data = json.loads(message)
            await messageHandler(data, websocket)
        except websockets.exceptions.ConnectionClosedOK:
            logging.debug("Connection closed")
            logging.debug("reconnecting...")
            asyncio.run(main())
        except Exception as err:
            logging.error("Error receiving ws: ", err)

# func parsing through message content
# should only look for JSON data with command "run-file"
#calls runFile() and sendOutput
# returns None
async def messageHandler(data, websocket):
    logging.debug("starting messageHandler()")
    try:
        if data.get("command") == "run-file":
            logging.debug("found run-file")
            if "file_name" in data and "file_content" in data: # required headers in JSON data that are constructed when json is sent
                logging.debug("found file_name and file_content")
                path = data["file_name"]
                forwardingToken = data["token"]
                logging.debug(f"obtained path: {path} and forwardingToken: {forwardingToken}")
                fileContent = base64.b64decode(data["file_content"]) # .py file transfers as base64 encoded string from frontend to backend to frontend
                with open(path, 'wb') as file:
                    file.write(fileContent)
                result = await runFile(path)
                await sendOutput(result, forwardingToken, websocket)
            else: 
                await sendOutput({"error": "JSON data is not structured correctly: please include file_name and file_content"}, forwardingToken, websocket)
    except Exception as err:
        logging.error(f"Error in messageHandler: {err}")

# func for running .py file given path
# returns dict with results of file
async def runFile(path):
    logging.debug("starting runFile()")
    try:
        if path.endswith('.py'):
            logging.debug("path ends with .py")
            logging.debug("running file")
            execute = subprocess.run(["python", path], capture_output = True, text = True)
            result = {
            "stdout": execute.stdout, # stdout is the output of the file i.e "Hello, World!"
            "stderr": execute.stderr, # stderr is the error output of the file i.e "SyntaxError: invalid syntax"
            "returncode": execute.returncode, # returncode is the return code of the file i.e 0 or 1 
        }
            logging.debug(f"file completed with result: {result}")
            os.remove(path) # remove file 
            return result
        else:
            return {"error": "unsupported file type: please use .py files"}
    except Exception as err:
        return {"error": str(err)} # return error as dict to parse as JSON
    
# func for sending file output data 
# returns None
async def sendOutput(sendData, forwardingToken, websocket):
    logging.debug("starting sendOutput()")
    try:
        logging.debug("starting payload()")
        payload =  await getPayload(sendData)
        payload["forwarding_token"] = forwardingToken
        logging.debug(f"added forwardingToken: {forwardingToken} to payload")
        await websocket.send(json.dumps(payload))
        logging.debug("output sent")
    except Exception as err:
        logging.error(f"Error sending output: {err}")

# main function for running all functions
# calls sendGPU() and listen() at once
# enables program to send GPU continuously and listen to websocket
# returns None
async def main():
    logging.info("main() started")
    try: 
        logging.debug(f"Connecting to websocket at {url}")
        async with websockets.connect(url) as websocket:
            logging.debug(f"connected to websocket: {websocket}")
            logging.info("starting send() and listen()")
            await asyncio.gather(send(websocket), listen(websocket))
    except Exception as err:
        logging.error("Websocket error: %s" % err)
         
if __name__ == "__main__":
    logging.getLogger(__name__)
    logging.basicConfig(filename='logs/logs.log', level=logging.INFO)
    logging.debug("Starting main()")
    asyncio.run(main())
    
