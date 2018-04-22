#!/usr/bin/env python
from __future__ import print_function
import os
import os.path
import re
import sys
import json
import inspect


#A global fail flag, used to fail the program on leathal errors
fail = False

HYSDS_IO_VALID_PARAM_TYPES = {
    "region": [],
    "text": [], 
    "number": [],
    "date": [],
    "datetime": [],
    "boolean": [],
    "enum": ["enumerables"],
    "email": [],
    "textarea": [],
    "container_version": ["version_regex"],
    "jobspec_version": ["version_regex"],
    "hysdsio_version": ["version_regex"]
}

def check_true(boolean,lethal,message):
    '''
    Check if boolean is true, and print message if not true
    @param boolean: result of condition
    @param lethal: should this cause an error and fail the program
    @message: message to print
    '''
    #Note: using global to fail program
    global fail
    if boolean:
        return
    printable = "[WARNING] {0}"
    if lethal:
        printable = "[ERROR] {0}"
        fail = True
    print(printable.format(message,file=sys.stderr))
def check_paired_args(prefix,spec,io):
    '''
    Check that the job-spec and hysds-io define the same parameters
    @param prefix - prefix
    @param spec - job-spec
    @param io - hysds-io
    '''
    spec_names = [param.get("name",None) for param in spec.get("params",[])]
    io_names = [param.get("name",None) for param in io.get("params",[])]
   
    for name in spec_names:
        check_true(not name is None, True, "{0} defines job-spec parameter with no 'name' field".format(prefix))
        check_true(name in io_names, True, "{0} defines job-spec parameter without match in hysds-io: {1}".format(prefix,name))
    for name in io_names:
        check_true(not name is None, True, "{0} defines hysds-io parameter with no 'name' field".format(prefix))
        check_true(name in spec_names, True, "{0} defines hysds-io parameter without match in job-spec: {1}".format(prefix,name))
def check_from(prefix,io):
    '''
    Check all the froms in the hysds-io file
    @param prefix - prefix
    @param io - io object
    '''
    valid_froms = ["submitter","passthrough","dataset_jpath","value"]
    valid_passes = ["name","query","username","priority","type","queue"]
    valid_es_top = ["_source","_id","_type","_version","_index","_score"]
    params = io.get("params",[])
    for param in params:
        check_true("name" in param,True,"{0} defines hysds-io parameter with no 'name' field".format(prefix))
        name = param.get("name","no-name")
        check_true("from" in param,True,"{0} defines hysds-io parameter, '{1}', with no 'from' field".format(prefix,name))
        frm = param.get("from","no-from")
        check_true(frm in valid_froms or frm.startswith("dataset_jpath"),True,"{0} defines hysds-io parameter, {1}, with bad 'from' field, {2}".format(prefix,name,frm))
        if frm == "value":
            check_true("value" in param,True,"{0} defines hysds-io value parameter, {1}, without value field".format(prefix,name))
        if frm == "passthrough":
            check_true(name in valid_passes,True,"{0} defines hysds-io passthrough parameter with invalid name, {1}, must be one of {2}".format(prefix,name,valid_passes))
        if frm.startswith("dataset_jpath"):
            split = frm.split(":")
            check_true(len(split) == 2, True, "{0} defines hysds-io dataset_jpath parameter, {1}, with invalid format: {2} does not match 'dataset_jpath:*".format(prefix,name,frm))
            if len(split) == 2:
                first = split[1].split(".")[0]
                check_true(first == "" or first in valid_es_top,True,"{0} defines hysds-io parameter, {1}, with dataset_jpath, {2}, that will not exist.".format(prefix,name,split[1]))
        if "lambda" in param:
            try:
                check_true(param["lambda"].startswith("lambda "), True, "{0} defines hysds-io lambda modifer for parameter, {1}, which does not equate to a lambda function".format(prefix,name))
                import functools
                import hysds_commons.lambda_builtins
                namespace = {"functools":functools}
                for nm in dir(hysds_commons.lambda_builtins):
                    if nm.startswith("__"):
                        continue
                    namespace[nm] = hysds_commons.lambda_builtins.__dict__[nm]
                fn = eval(param["lambda"],namespace,{})
                check_true(type(fn) == type(lambda arg: 1), True, "{0} defines hysds-io lambda modifer for parameter, {1}, which does not equate to a lambda function".format(prefix,name))
                argspec = inspect.getargspec(fn)
                check_true(len(argspec[0]) == 1, True, "{0} defines hysds-io lambda modifer for parameter, {1}, which does not except exactly 1 argument".format(prefix, name))
                try:
                    fn("Some test value")
                except NameError as ne:
                    if "global name" in str(ne) and "is not defined" in str(ne):
                        raise
                except Exception as e:
                    pass
            except Exception as e:
                check_true(False,True,"{0} defines hysds-io lambda modifer for parameter, {1}, which errors on compile. {2}:{3}".format(prefix,name,str(type(e)),e))
        #Chek type definitions
        param_type = param.get("type", "undefined")
        check_true(param_type != "undefined", False, "{0} defines hysds-io parameter {1} without a type".format(prefix,name))
        param_type = param.get("type", "text")
        check_true(param_type in HYSDS_IO_VALID_PARAM_TYPES.keys(), True, "{0} defines hysds-io parameter {1} with invalid type {2}".format(prefix, name, param_type))
        for field in HYSDS_IO_VALID_PARAM_TYPES.get(param_type,[]):
            check_true(field in param, True, "{0} defines hysds-io parameter {1} with type {2} but not required field {3}".format(prefix, name, param_type, field))
        default_value = param.get("default", "none")
        check_true(isinstance(default_value, basestring), True, "{0} defines hysds-io parameter {1} with default that is not a string.".format(prefix, name))
def check_to(prefix,spec):
    '''
     
    '''
    valid_tos = ["context","positional","localize"]
    params = spec.get("params",[])
    for param in params:
        check_true("name" in param,True,"{0} defines job-spec parameter with no 'name' field".format(prefix))
        name = param.get("name","no-name")
        check_true("destination" in param,True,"{0} defines job-spec parameter, '{1}', with no 'destination' field".format(prefix,name))
        to = param.get("destination","no-from")
        check_true(to in valid_tos,True,"{0} defines job-spec parameter, {1}, with bad 'destination' field, {2}".format(prefix,name,to))
    
def check_spec(prefix,spec):
    #Note: check params exists
    check_true("command" in spec,True,"{0} defines job-spec without command field".format(prefix))
    check_true("params" in spec,True,"{0} defines job-spec without params field".format(prefix))
    check_true("soft_time_limit" in spec,True,"{0} defines job-spec without soft time limit field".format(prefix))
    check_true("time_limit" in spec,True,"{0} defines job-spec without time limit field".format(prefix))
    #Deprecated names
    check_true("required-queues" not in spec,False,"{0} defines job-spec with deprecated 'required-queues'".format(prefix))
    check_true("recommened-queues" not in spec,False,"{0} defines job-spec with deprecated 'recommended-queues'".format(prefix))
    check_true("params" in spec,True,"{0} defines job-spec without params field".format(prefix))

def check_io(prefix,io):
    #Note: check params exists
    check_true("params" in io,True,"{0} defines hysds-io without params field".format(prefix))
    check_true("submission_type" in io,False,"{0} defines hysds-io without 'submission_type'".format(prefix))
    check_true(io.get("submission_type","individual") in ["individual","iteration"],True,"{0} defines hysds-io with illegal 'submission_type' of {1}".format(prefix,io.get("submission_type","individual")))
def pair(jsons):
    '''
    Pair the JSONS to the base name
    @param jsons - jsons dictionary
    @return: list of dictioaries
    '''
    objects = {}
    reg = re.compile("^.*/(.*)\.json\.?(.*)$")
    for k,v in jsons.iteritems():
        match = reg.match(k)
        name = match.group(2)
        f_type = match.group(1)
        if not name in objects:
            objects[name] = {}
        objects[name][f_type] = v
    for k,v in objects.iteritems():
        for f_type in ["hysds-io","job-spec"]:
            check_true(f_type in v,False,"{0} does not define a {1}.json".format(k,f_type))
    return objects
def json_formatted(files):
    '''
    Check JSON formatting
    @param files - files to loop through
    @return: name to JSON dict
    '''
    jsons = {} 
    for fle in files:
        try:
            with open(fle,"r") as fp:
                jsons[fle] = json.load(fp)
        except Exception as e:
            extra = "" if "No JSON object could be decoded" in str(e)  else "Probable a malformed literal. Fractional numbers must start with 0. "
            check_true(False,True,"Failed to validate JSON in: {0}. {3}{1}:{2}".format(fle,type(e),str(e),extra))
    return jsons

if __name__ == "__main__":
    '''
    Main functions
    '''
    if len(sys.argv) != 2:
         print("Usage:\n\t{0} <directory>".format(sys.argv[0]),file=sys.stderr)
         sys.exit(-1)
    directory = sys.argv[1]
    try:
        files = [os.path.join(directory,fle) for fle in os.listdir(directory) if os.path.isfile(os.path.join(directory,fle)) and ".json" in fle]
    except:
        files = []
    if len(files) == 0:
        print("[ERROR] No files found in directory: {0}".format(directory),file=sys.stderr)
        sys.exit(1)
    jsons = json_formatted(files)
    pairs = pair(jsons)
    for k,v in pairs.iteritems():
       if "job-spec" in v:
           check_spec(k,v["job-spec"])
           check_to(k,v["job-spec"])
       if "hysds-io" in v:
           check_io(k,v["hysds-io"])
           check_from(k,v["hysds-io"])
       if "job-spec" in v and "hysds-io" in v:
           check_paired_args(k,v["job-spec"],v["hysds-io"])
    if fail:
        sys.exit(1)
