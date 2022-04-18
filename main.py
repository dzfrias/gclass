import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import json
import webbrowser
from dataclasses import dataclass, field
from datetime import date, timedelta
from _thread import start_new_thread
from os import get_terminal_size

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


def format_day(day: date):
    return day.strftime(f"%B %-d{day_suffix(day.day)}")


@dataclass(order=True)
class Assignment:
    sort_index: date = field(init=False, repr=False)

    # Parameters
    name: str
    description: str = field(repr=False)
    due_date: date
    course: str
    attachment: str | None
    link: str

    def __post_init__(self):
        # Makes all assignments sorted by due_date
        self.sort_index = self.due_date

    def describe(self):
        print("Course: " + self.course)
        print(self.due_date.strftime(f"Due: {format_day(self.due_date)} %Y"))
        if self.attachment is not None:
            attachment = "Yes"
        else:
            attachment = "No"
        print(f"Attachment: {attachment}")
        print(f"\n{self.name}\n{'-' * len(self.name)}")
        print(self.description)

    def open(self):
        webbrowser.open(self.link)

    def open_attachment(self):
        if self.attachment is not None:
            webbrowser.open(self.attachment)
        else:
            print("No attachment to open!")

    def __str__(self):
        return f"{self.name} --- Due: {format_day(self.due_date)}"

    def as_dict(self):
        # Makes a copy of __dict__
        self_dict = dict(self.__dict__)
        self_dict["due_date"] = {
                "year": self.due_date.year,
                "month": self.due_date.month,
                "day": self.due_date.day
                }
        del self_dict["sort_index"]
        return self_dict


class AllAssignments:
    def __init__(self):
        self.service = authenticate()
        # Finds all courses of current user
        self.courses = self.get_courses()
        self.all_work = self.load_work()
        # Does this in the background so the user doesn't have to wait to see
        # their latest assignments every time
        start_new_thread(self.get_work, ())

    def get_courses(self) -> list[dict]:
        try:
            with open("ignored.txt") as f:
                # Ignores certain courses the user chooses
                IGNORE = f.readlines()
        except FileNotFoundError:
            IGNORE = []

        courses = self.service.courses().list(
                courseStates=["ACTIVE"], studentId="me",
                fields="courses(id,name)").execute()["courses"]
        return [course for course in courses if course["name"] not in IGNORE]

    @staticmethod
    def partial_input(user_command: str) -> str | None:
        VALID_COMMANDS = ("list", "exit", "look", "attachment", "open")
        for command in VALID_COMMANDS:
            # Sees if user input partially matches the command name
            matching = all([char == char2 for char, char2 in zip(command, user_command)])
            if command[:2] == user_command[:2] and matching:
                # Needs at least 2 characters for a command to be executed
                return command
        return None
    
    def get_assignment(self, index_1: int) -> Assignment:
        return sorted(self.all_work)[index_1 - 1]

    def run(self):
        # Commands that require target assignments work
        TARGET_COMMANDS = ("look", "attachment", "open")
        command = ""
        while command != "exit":
            inp = input("\n-> ").split()
            try:
                command = self.partial_input(inp[0])
            except IndexError:
                command = ""
            try:
                try:
                    target = int(inp[1])
                    if target - 1 < 0:
                        target = None
                except ValueError:
                    print("Target needs to be a number!")
                    continue
            except IndexError:
                target = None

            if command in TARGET_COMMANDS and target is None:
                # Prevents invalid targets
                print(f"Command `{command}` needs a valid target!")
                continue

            if command == "list":
                bar_printed = False
                for number, work in enumerate(sorted(self.all_work), 1):
                    if not bar_printed and work.due_date >= date.today():
                        # Prints a header bar with the current day
                        term_columns = get_terminal_size()[0]
                        print("-" * term_columns)
                        print("TODAY".center(term_columns), end="\r")
                        print(format_day(date.today()))
                        print("-" * term_columns)
                        bar_printed = True
                    print(f"{number}. {work}")

            elif command == "look":
                self.get_assignment(target).describe()

            elif command == "attachment":
                self.get_assignment(target).open_attachment()

            elif command == "open":
                self.get_assignment(target).open()

            elif command != "exit":
                print("Invalid command")

    @staticmethod
    def load_work() -> list[Assignment]:
        current_work = []
        try:
            with open("assignments.json") as f:
                for work in json.load(f)["assignments"]:
                    work["due_date"] = date(**work["due_date"])
                    current_work.append(Assignment(**work))
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
                    fields='studentSubmissions(courseWorkId,assignmentSubmission/attachments/driveFile/alternateLink,alternateLink)').execute()
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
                            try:
                                attachment = result["assignmentSubmission"]["attachments"][0]["driveFile"]["alternateLink"]
                            except KeyError:
                                attachment = None
                            current_work.append(Assignment(
                                    work["title"],
                                    work.get(
                                        "description",
                                        "No description for this assignment"
                                        ),
                                    date(**work["dueDate"]),
                                    course["name"],
                                    attachment,
                                    result["alternateLink"]))
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

