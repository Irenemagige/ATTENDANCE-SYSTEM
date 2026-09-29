class ApiConstants {
  static const String mode = "prod"; // dev | emulator | prod

  static String get baseUrl {
    switch (mode) {
      case "dev":
        return "http://127.0.0.1:8000/api/";
      case "emulator":
        return "http://10.0.2.2:8000/api/";
      case "prod":
        return "https://attendance-system-production-5479.up.railway.app/api/";
      default:
        return "http://127.0.0.1:8000/api/";
    }
  }
}