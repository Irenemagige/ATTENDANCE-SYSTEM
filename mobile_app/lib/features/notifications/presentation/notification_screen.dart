import 'package:flutter/material.dart';
import 'package:mobile_app/features/dashboard/data/dashboard_service.dart';
import 'package:mobile_app/core/storage/storage_service.dart';


class NotificationScreen extends StatefulWidget {
  final VoidCallback? onNotificationsRead;

  const NotificationScreen({
    super.key,
    this.onNotificationsRead,
  });

  @override
  State<NotificationScreen> createState() =>
      _NotificationScreenState();
}


class _NotificationScreenState extends State<NotificationScreen> {


  List<dynamic> notifications = [];

  int unreadCount = 0;

  bool isLoading = true;



  @override
void initState() {
  super.initState();
  loadNotifications();
}

  
  Future<void> markAllRead() async {
  final token = await StorageService.getAccessToken();

    if (token == null) {
      return;
    }

    final result =
      await DashboardService().markAllNotificationsRead(token);

      print("MARK ALL READ RESULT: $result");
    }






  Future<void> loadNotifications() async {

  setState(() {
    isLoading = true;
  });

  final token = await StorageService.getAccessToken();

  if (token == null) {
    setState(() {
      isLoading = false;
    });
    return;
  }


  final result =
      await DashboardService()
          .getNotifications(token);


  if (!mounted) return;


  if (result["success"] == true) {
  final data = result["data"] as Map<String, dynamic>;

  setState(() {
    unreadCount = data["unread_count"] ?? 0;

    notifications =
        List<dynamic>.from(
          data["notifications"] ?? [],
        );

    isLoading = false;
  });

  // Mark notifications as read AFTER they have been loaded/displayed.
  await markAllRead();

if (!mounted) return;

setState(() {
  unreadCount = 0;
});

widget.onNotificationsRead?.call();

} else {

    setState(() {
      isLoading = false;
    });

  }

}

  @override
  Widget build(BuildContext context) {


    return Scaffold(

      appBar: AppBar(

        title: const Text(
        "Notifications"
        ),

      ),


      body: isLoading

          ? const Center(
              child:
              CircularProgressIndicator(),
            )


          : notifications.isEmpty

              ? const Center(
                  child:
                  Text(
                    "No notifications"
                  ),
                )


              : ListView.builder(

                  itemCount:
                      notifications.length,


                  itemBuilder:
                      (context,index){


                    final item =
                        notifications[index];


                    return Card(

                      child: ListTile(

                        leading: const Icon(
                        Icons.notifications,
                        color: Colors.blue,  ),


                        title: Text(
                        item["title"]?.toString() ?? '',
                        ),

                        subtitle: Text(
                        item["message"]?.toString() ?? '',
                        ),

                      ),

                    );


                  },

                ),


    );

  }

}