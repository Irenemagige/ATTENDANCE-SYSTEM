import 'package:flutter/material.dart';
import 'package:mobile_app/core/storage/storage_service.dart';
import 'package:mobile_app/features/dashboard/data/dashboard_service.dart';


class AttendanceHistoryScreen extends StatefulWidget {
  const AttendanceHistoryScreen({super.key});

  @override
  State<AttendanceHistoryScreen> createState() =>
      _AttendanceHistoryScreenState();
}


class _AttendanceHistoryScreenState
    extends State<AttendanceHistoryScreen> {


  final DashboardService dashboardService =
      DashboardService();


  Map<String, dynamic>? history;

  bool loading = true;

  String? errorMessage;



  @override
  void initState() {
    super.initState();

    loadHistory();
  }



  Future<void> loadHistory() async {

    try {

      final token =
          await StorageService.getAccessToken();


      if(token == null){

        setState(() {

          loading = false;

          errorMessage =
              "Authentication token missing";

        });

        return;
      }



      final result =
          await dashboardService.getAttendanceHistory(token);



      if(result['success'] == true){


        setState(() {

          history =
              Map<String,dynamic>.from(
                result['data']
              );

          loading = false;

        });


      }
      else {


        setState(() {

          loading = false;

          errorMessage =
              "Failed to load attendance history";

        });


      }


    }

    catch(e){

      setState(() {

        loading = false;

        errorMessage =
            e.toString();

      });

    }

  }



  @override
  Widget build(BuildContext context) {


    if(loading){

      return const Center(
        child: CircularProgressIndicator(),
      );

    }



    if(errorMessage != null){

      return Center(

        child: Column(

          mainAxisAlignment:
              MainAxisAlignment.center,

          children: [


            Text(
              errorMessage!,
              textAlign: TextAlign.center,
            ),


            const SizedBox(height: 15),


            ElevatedButton(

              onPressed: loadHistory,

              child:
                  const Text("Retry"),

            )


          ],

        ),

      );

    }



    final overall =
        history?['overall_percentage'] ?? 0;



    final subjects =
      history?['subject_performance'] ?? [];

    final recent =
      history?['history'] ?? [];




    return Scaffold(

      backgroundColor:
          const Color(0xFFF8FAFC),


      body: RefreshIndicator(

        onRefresh: loadHistory,


        child: ListView(

          padding:
              const EdgeInsets.all(16),


          children: [



            const Text(

              "Attendance Summary",

              style: TextStyle(

                fontSize: 22,

                fontWeight:
                    FontWeight.bold,

              ),

            ),



            const SizedBox(height:16),




            Card(

              child: ListTile(

                title:
                    const Text(
                      "Overall Attendance",
                    ),


                trailing:

                    Text(

                      "$overall%",

                      style:
                          const TextStyle(

                        fontSize:20,

                        fontWeight:
                            FontWeight.bold,

                      ),

                    ),

              ),

            ),




            const SizedBox(height:25),




            const Text(

              "Subject Performance",

              style: TextStyle(

                fontSize:18,

                fontWeight:
                    FontWeight.bold,

              ),

            ),



            const SizedBox(height:10),




            Card(

              child: Column(

                children:

                List.generate(

                  subjects.length,

                  (index){


                    final subject =
                        subjects[index];


                    return ListTile(

                      title:
                          Text(
                            subject['subject']
                                .toString(),
                          ),


                      trailing:
                          Text(

                            "${subject['percentage']}%",

                            style:
                                const TextStyle(

                              fontWeight:
                                  FontWeight.bold,

                            ),

                          ),

                    );


                  },

                ),

              ),

            ),




            const SizedBox(height:25),




            const Text(

              "Recent Attendance",

              style: TextStyle(

                fontSize:18,

                fontWeight:
                    FontWeight.bold,

              ),

            ),




            const SizedBox(height:10),




            Card(

              child: Column(

                children:

                List.generate(

                  recent.length,

                  (index){


                    final attendance =
                        recent[index];



                    final status =
                        attendance['status']
                            .toString();



                    return ListTile(
  title: Text(
    attendance['subject'].toString(),
  ),

  subtitle: Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        attendance['date'].toString(),
      ),

      const SizedBox(height: 6),

      Text(
        "Session Attendance: "
        "${attendance['attendance_percentage']}% — "
        "${status.replaceAll('_', ' ')}",
      ),

      const SizedBox(height: 4),

      Text(
        "Subject Attendance: "
        "${attendance['subject_attendance_percentage']}%",
      ),

      const SizedBox(height: 4),

    ],
  ),

  trailing: Text(
    status.replaceAll('_', ' '),
    style: TextStyle(
      fontWeight: FontWeight.bold,

      color: status == "PRESENT"
          ? Colors.green
          : status == "LATE"
              ? Colors.orange
              : Colors.red,
    ),
  ),
);


                  },

                ),

              ),

            ),



          ],

        ),

      ),

    );


  }

}

     String formatTime(dynamic value) {
  if (value == null) {
    return '-';
  }

  final dateTime = DateTime.tryParse(
    value.toString(),
  );

  if (dateTime == null) {
    return '-';
  }

  final hour =
      dateTime.hour.toString().padLeft(2, '0');

  final minute =
      dateTime.minute.toString().padLeft(2, '0');

  return '$hour:$minute';
}