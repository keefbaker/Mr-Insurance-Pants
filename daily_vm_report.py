#
# Name : daily_vm_report
# Creation Date : 24/11/2016
# Created By : Keith Baker
# Purpose : Report on any changes in the VMWare environment

"""
Report on any changes in the VMWare environment and email out the results
"""
import sys
import atexit
import ssl
import smtplib
import datetime

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from pyVim import connect
from pyVmomi import vmodl
from pyVmomi import vim
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
##########################################################

message_to_mail = []
Base = declarative_base()

class vm_record(Base):
    __tablename__ = "vm_record"
    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    resource_pool = Column(String(250))
    ram_reservation = Column(String(250))
    cpu_reservation = Column(String(250))
    ram = Column(String(250))
    cpus = Column(String(250))
    number_of_disks = Column(Integer)

engine = create_engine('sqlite:///vmdatabase.db')
Base.metadata.create_all(engine)

def print_vm_info(vm, hostip, depth=1, max_depth=10):
    """
    Print information for a particular virtual machine or recurse into a
    folder with depth protection
    """

    # if this is a group it will have children. if it does, recurse into them
    # and then return
    if hasattr(vm, 'childEntity'):
        if depth > max_depth:
            return
        vmList = vm.childEntity
        for c in vmList:
            print_vm_info(c, hostip, depth + 1)
        return
    dbsession = parse_all_that_lovely_data(vm, hostip)
    dbsession.commit()

def parse_all_that_lovely_data(vm, hostip):
    """
    Turn the data into something useful and if appropriate, add to the database.
    """
    Base.metadata.bind = engine
    DBSession = sessionmaker()
    DBSession.bind = engine
    session = DBSession()
    try:
        record = session.query(vm_record).filter(vm_record.name == vm.summary.config.name).one()
    except:
        record = None
    if record is None:
        new_vm(vm, session)
    else:
        big_comparison_time(vm, session, record, hostip)
    return session

def big_comparison_time(vm, session, record, hostip):
    """
    Compares all fields, adds to the problem list if there is one 
    and replaces the record if it's wrong.
    """
    updateit = False
    try:
        if record.resource_pool != vm.resourcePool.name:
            message_to_mail.append( "Vserver:" +hostip + ", guest: "+  record.name + " has had it's resource pool changed from " + record.resource_pool + " to " + vm.resourcePool.name + ".")
            updateit = True
    except Exception as e:
        print str(e), "problem parsing resource pool"
    try:
        if str(record.ram_reservation) != str(vm.config.memoryAllocation.reservation):
            message_to_mail.append( "Vserver:" +hostip + ", guest: "+  record.name + " has had it's ram reservation changed from " + str(record.ram_reservation) + " to " + str(vm.config.memoryAllocation.reservation) + ".")
            updateit = True
    except Exception as e:
        print str(e), "problem parsing ram reservation"
    try:
        if str(record.cpu_reservation) != str(vm.config.cpuAllocation.reservation):
            message_to_mail.append( "Vserver:" +hostip + ", guest: "+  record.name + " has had it's cpu reservation changed from " + str(record.cpu_reservation) + " to " + str(vm.config.cpuAllocation.reservation) + ".")
            updateit = True
    except Exception as e:
        print str(e), "problem parsing cpu reservation"
    try:
        if str(record.ram) != str(vm.summary.config.memorySizeMB):
            message_to_mail.append( "Vserver:" +hostip + ", guest: "+  record.name + " has had it's ram changed from " + str(record.ram) + " to " + str(vm.summary.config.memorySizeMB) + ".")
            updateit = True
    except Exception as e:
        print str(e), "problem parsing ram"
    try:
        if str(record.cpus) != str(vm.summary.config.numCpu):
            message_to_mail.append( "Vserver:" +hostip + ", guest: "+  record.name + " has had it's cpu changed from " + str(record.cpus) + " to " + str(vm.summary.config.numCpu) + ".")
            updateit = True
    except Exception as e:
        print str(e), "problem parsing cpu"
    try:
        if record.number_of_disks != vm.summary.config.numVirtualDisks:
            message_to_mail.append( "Vserver:" +hostip + ", guest: "+  record.name + " has had it's number of disks changed from " + record.number_of_disks + " to " + vm.summary.config.numVirtualDisks + ".")
            updateit = True
    except Exception as e:
        print str(e), "problem parsing number of disks"
    if updateit is True:
        session.delete(record)
        new_vm(vm, session, False)

def new_vm(vm, session, new=True):
    """
    The record in the database isn't there or is wrong.
    Let's sort that out.
    """
    try:
        add_this_vm = vm_record(name=vm.summary.config.name, 
                                resource_pool=vm.resourcePool.name, 
                                ram_reservation=vm.config.memoryAllocation.reservation,
                                cpu_reservation=vm.config.cpuAllocation.reservation,
                                ram=vm.summary.config.memorySizeMB,
                                cpus=vm.summary.config.numCpu,
                                number_of_disks=vm.summary.config.numVirtualDisks)
        session.add(add_this_vm)
        if new is True:
            message_to_mail.append("new VM " + vm.summary.config.name + " was added to resource pool " + vm.resourcePool.name + " with a spec of " + str(vm.summary.config.numCpu) + "cpus and " + str(vm.summary.config.memorySizeMB) + "Mb RAM." )
    except:
        pass

def parse_service_instance(service_instance, hostip):
    """
    Return all virtual machines
    """

    content = service_instance.RetrieveContent()
    object_view = content.viewManager.CreateContainerView(content.rootFolder,
                                                          [], True)
    for obj in object_view.view:
        if isinstance(obj, vim.VirtualMachine):
            print_vm_info(obj, hostip)

    object_view.Destroy()
    return
def get_all_the_config():
    hosts = []
    try:    
        with open("config.ini", "r") as config:
            bang = 0
            for line in config.readlines():
                if line.startswith("#"):
                    bang += 1
                if bang < 1 and not line.startswith("#"):
                    data = line.split(":")
                    address_list = [ x.strip() for x in data[1].split(",")]
                elif bang > 0 and not line.startswith("#"):
                    try:
                        data = line.split(",")
                        if len(data[0]) > 3:
                            hosts.append({"address" : data[0].strip(), 
                                          "user" : data[1].strip(), 
                                          "password" : data[2].strip(), 
                                          "port" : data[3].strip()})
                    except:
                        print "There was an exception when processing:", data, ": Possibly there was a field missing"

    # Error messages to show problems with the config.
    except:
        print "There doesn't seem to be a config.ini in this directory"
        sys.exit(1)
    return address_list, hosts

def main(host):
    """
    Primary connection and loop
    """

    try:
        context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        context.verify_mode = ssl.CERT_NONE
        service_instance = connect.SmartConnect(host=host["address"],
                                                user=host["user"],
                                                pwd=host["password"],
                                                port=int(host["port"]),
                                                sslContext=context)
        if not service_instance:
            print("Could not connect to the specified host using specified "
                  "username and password")
            return -1
        atexit.register(connect.Disconnect, service_instance)

        parse_service_instance(service_instance, host["address"])
    except vmodl.MethodFault as e:
        print("Caught vmodl fault : {}".format(e.msg))
        return -1
    return 0

def mailout(message_to_mail, people_to_send_to):
    """
    Send email. 
    """
    fromaddress = "VMWareChangeReport@company.com"
    msg = MIMEMultipart()
    msg['Subject'] = 'VMWare Change Report for ' + str(datetime.date.today())
    msg['From'] = fromaddress
    msg['To'] = ", ".join(people_to_send_to)
    preamble = """
The following Changes have been detected in the VMWare environment:
=============================================================
> """ + "\n> ".join(message_to_mail)         
    msg.attach(MIMEText(preamble))
    s = smtplib.SMTP('localhost')
    s.sendmail(fromaddress, people_to_send_to, msg.as_string())
    s.quit()

# Start program
if __name__ == "__main__":
    addresses, hosts = get_all_the_config()
    for host in hosts:
        main(host)
    if len(message_to_mail) > 0:
        mailout(message_to_mail, addresses)
