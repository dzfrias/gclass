import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from _thread import start_new_thread

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/classroom.courses.readonly',
          'https://www.googleapis.com/auth/classroom.coursework.me',
          'https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly']


def day_suffix(day) -> str:
    date_suffix = ("th", "st", "nd", "rd")

    if day % 10 in (1, 2, 3) and day not in (11, 12, 13):
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
    
    def as_dict(self):
        return {"name": self.name,
                "description": self.description,
                "due_date": {
                    "year": self.due_date.year,
                    "month": self.due_date.month,
                    "day": self.due_date.day
                    }
                }


class AllAssignments:
    def __init__(self):
        try:
            with open("ignored.txt") as f:
                # Ignores certain courses the user chooses
                IGNORE = f.readlines()
        except FileNotFoundError:
            IGNORE = []

        self.service = authenticate()
        # Finds all courses of current user
        self.courses = self.service.courses().list(
                courseStates=["ACTIVE"], studentId="me",
                fields="courses(id,name)").execute()["courses"]
        self.courses = [course for course in self.courses if course["name"] not in IGNORE]
        self.all_work = self.load_work()
        # Does this in the background so the user doesn't have to wait to see
        # their latest assignments every time
        start_new_thread(self.get_work, ())

    @staticmethod
    def partial_input(user_command):
        VALID_COMMANDS = ("list", "exit")
        for command in VALID_COMMANDS:
            matching = all([char == char2 for char, char2 in zip(command, user_command)])
            if command[:2] == user_command[:2] and matching:
                return command

    def run(self):
        command = ""
        while command != "exit":
            command = self.partial_input(input("\n-> "))
            if command == "list":
                for number, work in enumerate(self.all_work, 1):
                    print(f"{number}. {work}")
            elif command != "exit":
                print("Invalid command")

    @staticmethod
    def load_work() -> list[Assignment]:
        current_work = []
        try:
            with open("assignments.json") as f:
                for work in json.load(f)["assignments"]:
                    current_work.append(
                            Assignment(
                                work["name"],
                                work["description"],
                                date(**work["due_date"])
                                )
                            )
        except FileNotFoundError:
            pass
        return current_work

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
                    # Cuts off the assignments not within the range
                    classwork = classwork[:index]

            for result in results["studentSubmissions"]:
                for work in classwork:
                    if work["id"] == result["courseWorkId"]:
                        try:
                            current_work.append(Assignment(
                                    work["title"],
                                    work.get(
                                        "description",
                                        "No description for this assignment"
                                        ),
                                    date(**work["dueDate"])))
                        except KeyError:
                            pass
                        break

        if self.all_work != current_work:
            # Moves cursor to the line above and resets prompt
            print("\n\x1b[0G\x1b[1ACurrent work updated! Refresh using `list`",
                    end="\n-> ")
            self.all_work = current_work
            with open("assignments.json", "w") as f:
                all_assignments_dict = {
                        "assignments": [
                            work.as_dict() for work in self.all_work
                            ]
                        }
                json.dump(all_assignments_dict, f, indent=4)


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

