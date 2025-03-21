import GPUtil
import json
import asyncio
import websockets
import subprocess
import base64
import os

#TODO: use tkinter to make a GUI
#TODO: create error function
#TODO: test on home computer
#TODO: implement docker

gpuMaxLoad = 0.5 # 50% load; should later be user defined
gpuMaxMemory = 0.5 # 50% memory; should later be user defined
gpuJasonPath = 'gpu_info.json' # constant path for GPU info
fileResultPath = 'file_result.json' # constant path for file result
url = 'ws://localhost:5050/gpu_info' # websocket URL (currently placeholder)

# func for getting GPU info
# returns list of dicts with GPU info
# returns none if GPU load or memory exceeds max
async def getGPUs():
    gpuList = []
    gpus = GPUtil.getGPUs() 
    for gpu in gpus: # will parse through all data for every GPU in system 
        info = {
            "load": gpu.load * 100, # saves load as percentage. subject to change
            "memory": gpu.memoryMax / gpu.memoryFree # saves in percentage. subject to change
        }
        if info["load"] > gpuMaxLoad or info["memory"] < gpuMaxMemory:
            return None
        gpuList.append(info)
    return gpuList

# func for writing to JSON file given path and data
# returns None
async def writeToJSON(path, jsonData):
    with open(path, 'w') as jsonFile:
        json.dump(jsonData, jsonFile, indent = 4)

# func for running .py file given path
# returns dict with results of file
async def runFile(path):
    try:
        if path.endswith('.py'):
            execute = subprocess.run(["python", path], capture_output = True, text = True)
            result = {
            "stdout": execute.stdout, # stdout is the output of the file i.e "Hello, World!"
            "stderr": execute.stderr, # stderr is the error output of the file i.e "SyntaxError: invalid syntax"
            "returncode": execute.returncode # returncode is the return code of the file i.e 0 or 1 
        }
            os.remove(path) # remove file 
            return result
        else:
            return {"error": "unsupported file type: please use .py files"}
    except Exception as err:
        return {"error": str(err)} # return error as dict to parse as JSON

# func for listening to websocket
# should only look for JSON data with command "run-file"
#calls runFile() and writeToJSON() and sendInfo()
# returns None
async def listenRequests(websocket):
    async for message in websocket:
        try:
            data = json.loads(message) 
            if data.get("command") == "run-file":
                if "file_name" in data and "file_content" in data: # required headers in JSON data that are constructed in server backend
                    path = data["file_name"]
                    fileContent = base64.b64decode(data["file_content"]) # .py file transfers as base64 encoded string from frontend to backend to frontend
                    with open(path, 'wb') as file:
                        file.write(fileContent)
                    result = await runFile(path, websocket)
                    await writeToJSON(fileResultPath, result)
                    await sendInfo(fileResultPath, websocket)
                else: 
                    await websocket.send(json.dumps({"error": "JSON data is not structured correctly: please include file_name and file_content"}))
        except Exception as err:
            print(err)

# func for sending JSON data 
# returns None
async def sendInfo(filePath, websocket):
    try:
        with open(filePath, 'r') as jsonFile:
            fileLeaving = json.load(jsonFile)
        await websocket.send(json.dumps(fileLeaving))
    except Exception as err:
        print(err)

# func for sending GPU info every 5 minutes
# calls getGPUs() and writeToJSON() and sendInfo()
# returns None
async def sendGPU(websocket):
    while True:
        gpuInfo = await getGPUs()
        if gpuInfo: 
            await writeToJSON(gpuJasonPath, gpuInfo)
            await sendInfo(gpuJasonPath, websocket)
        await asyncio.sleep(300)

# main function for running all functions
# calls sendGPU() and listenRequests() at once
# enables program to send GPU continuously and listen to websocket
# returns None
async def main():
    try:
        async with websockets.connect(url) as websocket:
            await asyncio.gather(sendGPU(websocket), listenRequests(websocket))
    except Exception as err:
        print("ws error: ", err)
         
if __name__ == "__main__":
    asyncio.run(main())
    
