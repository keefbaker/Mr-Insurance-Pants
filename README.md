# VMWare Change report

### Requirements

Python modules:

- pyvmomi
- sqlalchemy

On the running machine

- SQLite
- An email insance such as postfix (or reconfigure the host in the script)

### Function

It will communicate with VCenter servers as configured in the *config.ini*, store the machine configs in an SQLite database and compare against what's stored to email out if there have been any changes.

It's designed to run once per day but can be run any number of times, it will only mail out if something has changed.

The list of email addresses to send to is in the *config.ini* and the from address and email host are in the code/ 