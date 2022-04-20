# gclass
View and open Google Classroom assignments from the command line.

## Initial Note
Because this uses a Google API, credentials are needed for use. Credentials can't be provided through GitHub, so creating fresh Google Classroom API credentials are necessary.

## Commands
All listed commands can be abbreviated to two or more characters. Example: to execute the list command, there are options of `li`, `lis` or `list`.
### Standalone Commands
These commands are to be run without any arguments.
- `list`
  - List current assignments, ordered by date
- `course`
  - Refresh course list
- `status`
  - View status of collecting assignments
- `exit`
  - Quit the code

### Target Commands
These commands are of the form: `{command} {num}` where `num` is the assignment's number corresponding with the `list` command.
- `look`
  - View an assignment, described in detail
- `attachment`
  - Open an assignment's attachment in the browser
- `open`
  - Open an assignment in the browser

### Misc
- `ignore`
  - Ignore the given course when listing assignments
  - Takes in one argument, which is the course to ignore (by name)
- `remove`
  - Remove a course from being ignored
  - Takes in one argument, which is the course to remove the ignored status from
