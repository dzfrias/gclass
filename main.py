import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from dataclasses import dataclass, field
from datetime import date, timedelta
from _thread import start_new_thread

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/classroom.courses.readonly',
          'https://www.googleapis.com/auth/classroom.coursework.me',
          'https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly']


def day_suffix(day):
    date_suffix = ["th", "st", "nd", "rd"]

    if day % 10 in [1, 2, 3] and day not in [11, 12, 13]:
        return date_suffix[day % 10]
    else:
        return date_suffix[0]


@dataclass
class Assignment:
    name: str
    description: str = field(repr=False)
    due_date: date

    def describe(self):
        return self.description

    def __str__(self):
        formatted_date = self.due_date.strftime(
                f"%B %-d{day_suffix(self.due_date.day)}")
        return f"{self.name} --- Due: {formatted_date}"


class AllAssignments:
    def __init__(self):
        try:
            with open("ignored.txt") as f:
                IGNORE = f.readlines()
        except FileNotFoundError:
            IGNORE = []

        self.service = authenticate()
        self.courses = self.service.courses().list(
                courseStates=["ACTIVE"], studentId="me",
                fields="courses(id,name)").execute()["courses"]
        self.courses = [course for course in self.courses if course["name"] not in IGNORE]
        self.all_work = []
        start_new_thread(self.get_work, ())

    def run(self):
        command = ""
        while command != "exit" and command != "ex":
            print()
            command = input("-> ")
            if command == "list":
                if self.all_work:
                    for number, work in enumerate(self.all_work, 1):
                        print(f"{number}. {work}")
                else:
                    print("Still gathering data...")
            elif command != "exit" and command != "ex":
                print("Invalid command")

    def get_work(self):
        current_work = []

        for course in self.courses:
            course_id = course["id"]

            results = self.service.courses().courseWork().studentSubmissions().list(
                    courseId=course_id, courseWorkId="-", userId="me",
                    states=["CREATED", "RECLAIMED_BY_STUDENT"],
                    fields='studentSubmissions(courseWorkId)').execute()
            if not results:
                continue

            classwork = self.service.courses().courseWork().list(
                    courseId=course_id,
                    orderBy="dueDate",
                    fields='courseWork(dueDate,id,title,description)').execute()["courseWork"]
            today = date.today()
            # Creates a range of days one week before and after the current day
            week_range = [today - timedelta(days=i) for i in range(-7, 8)]
            for index, work in enumerate(classwork):
                if "dueDate" not in work or date(**work["dueDate"]) not in week_range:
                    classwork = classwork[:index]

            for result in results["studentSubmissions"]:
                for work in classwork:
                    if work["id"] == result["courseWorkId"]:
                        try:
                            current_work.append(Assignment(
                                    work["title"],
                                    work.get("description", "None"),
                                    date(**work["dueDate"])))
                        except KeyError:
                            pass
                        break
        self.all_work = current_work


def authenticate():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('classroom', 'v1', credentials=creds)


if __name__ == '__main__':
    AllAssignments().run()

