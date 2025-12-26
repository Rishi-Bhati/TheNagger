
import asyncio
import logging
from database import Database
from config import DATABASE_URL
import statistics

async def check_metrics():
    db = Database(DATABASE_URL)
    await db.connect()
    
    try:
        async with db.acquire_connection() as conn:
            # Get last 50 metrics
            rows = await conn.fetch('''
                SELECT command, processing_time_ms, timestamp 
                FROM bot_metrics 
                ORDER BY timestamp DESC 
                LIMIT 50
            ''')
            
            print(f"{'Command':<15} | {'Time (ms)':<10} | {'Timestamp'}")
            print("-" * 50)
            
            times_by_cmd = {}
            
            for row in rows:
                cmd = row['command']
                time_ms = row['processing_time_ms']
                ts = row['timestamp'].strftime("%H:%M:%S")
                print(f"{cmd:<15} | {time_ms:<10.2f} | {ts}")
                
                if cmd not in times_by_cmd:
                    times_by_cmd[cmd] = []
                times_by_cmd[cmd].append(time_ms)
                
            print("\n--- Summary ---")
            for cmd, times in times_by_cmd.items():
                avg_time = statistics.mean(times)
                max_time = max(times)
                print(f"{cmd:<15}: Avg {avg_time:.2f}ms, Max {max_time:.2f}ms")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(check_metrics())
