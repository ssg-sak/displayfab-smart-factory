// Lesson 3: if / else if / for
// Python의 if, for i in range() 와 같다.
//
// 오늘 볼 것 세 개:
// 1. if        — 설비 상태에 따라 말이 바뀐다
// 2. else if   — STOP 이면 PROCESS를 거절한다
// 3. for       — heartbeat를 3번 보낸 것처럼 찍는다

class Program
{
    static void Main()
    {
        string equipmentId = "PROC-01";
        string status = "IDLE";
        string mode = "heartbeat";

        Console.WriteLine("DisplayFab C# lesson 3");
        Console.WriteLine($"{equipmentId} status={status} mode={mode}");

        // Python: if status == "STOP":
        if (status == "STOP")
        {
            Console.WriteLine("PROCESS rejected — EQUIPMENT_STOPPED");
        }
        else if (status == "MAINTENANCE")
        {
            Console.WriteLine("PROCESS rejected — EQUIPMENT_MAINTENANCE");
        }
        else
        {
            Console.WriteLine("PROCESS ok — IDLE/RUN 은 받는다");
        }

        // Python: if mode == "heartbeat":
        if (mode == "heartbeat")
        {
            // Python: for i in range(1, 4):
            for (int i = 1; i <= 3; i++)
            {
                Console.WriteLine($"heartbeat {i} {equipmentId}");
            }
        }
        else if (mode == "process")
        {
            Console.WriteLine($"{equipmentId} PROCESS EVAP");
        }
    }
}
