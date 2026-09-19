// Lesson 1: 프로그램이 시작되면 Main이 한 번 실행된다.
// Python의 print() 가 C#에서는 Console.WriteLine() 이다.

class Program
{
    static void Main()
    {
        string equipmentId = "PROC-01";
        string status = "IDLE";

        Console.WriteLine("DisplayFab C# lesson 1");
        Console.WriteLine($"{equipmentId} is {status}");
    }
}
