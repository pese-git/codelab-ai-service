/// Calculator utility class for task_015
class Calculator {
  /// Add two numbers
  int add(int a, int b) => a + b;
  
  /// Subtract two numbers
  int subtract(int a, int b) => a - b;
  
  /// Multiply two numbers
  int multiply(int a, int b) => a * b;
  
  /// Divide two numbers
  double divide(int a, int b) {
    if (b == 0) throw ArgumentError('Cannot divide by zero');
    return a / b;
  }
}
