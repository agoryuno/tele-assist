import asyncio
import time
from datetime import datetime


waiting = False

# Define a synchronous (blocking) function
def blocking_function():
    time.sleep(2)  # Simulate a blocking operation
    return 'Blocking call result'

async def async_function():
    global waiting
    print (datetime.now(), waiting)
    loop = asyncio.get_event_loop()
    # Run the synchronous function in a separate thread
    waiting = True
    future = loop.run_in_executor(None, blocking_function)
    # Wait for the result of the synchronous function
    result = await future
    print(result)
    waiting = False

async def main():
    await async_function()
    

# Run the main function
asyncio.run(main())
asyncio.run(main())