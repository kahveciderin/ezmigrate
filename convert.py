import threading
import psycopg2
import pymongo
import json
import copy

db_settings = {}


def con_pql(dbname):
    try:
        return psycopg2.connect(user=db_settings["dbsetup"]["username"],
                                password=db_settings["dbsetup"]["password"],
                                host=db_settings["dbsetup"]["host"],
                                port=db_settings["dbsetup"]["port"],
                                database=dbname)
    except:
        print("Could not connect to the database {0}. Skipping...".format(dbname))
        return -1


def get_list_keyed_obj(obj, namespace):
    aaret = obj
    for name in namespace:
        aaret = aaret[name]
    return aaret

def glkol(obj, namespace, last):
    if last.startswith('$$'):
        if last.startswith('$$lindex-'):
            indexNum = int(last.split('-')[1])
            theNum = 0
            for rhnum in reversed(namespace):
                if(type(rhnum) is int):
                    indexNum -= 1
                if indexNum < 0:
                    theNum = rhnum
                    break
            return theNum
    else:
        return get_list_keyed_obj(obj, namespace)[last]

def check_list_keyed_object(obj, namespace):
    aaret = obj
    for name in namespace:
        if type(name) is str and name.startswith('$$'):
            continue
        if type(aaret) is list:
            if len(aaret) <= name:
                return {}
        else: #dict
            if name not in aaret:
                return {}
        aaret = aaret[name]
    return aaret


def clkol(obj, namespace, last):
    if last.startswith('$$'):
        return True
    else:
        return last in check_list_keyed_object(obj, namespace)

def recursive_exec(doc, operations, wf, pdb):
    for operation in operations:
        working_field = wf
        if(operation[0] == '$'): # this is a field name in the current document
            working_field.append(operation[1:])
            recursive_exec(doc, copy.copy(operations[operation]), copy.copy(working_field), pdb)
        elif(operation == "for"):
            for_index = 0
            for ops in operations[operation]:
                new_wf = copy.copy(working_field)
                new_wf.append(for_index)
                recursive_exec(doc, copy.copy(ops), copy.copy(new_wf), pdb)
                for_index += 1
        elif(operation == "insert"):
            table_name = operations[operation]["name"]
            in_vals = {}
            ivl_vals = {}
            for ivl in operations[operation]["fields"]:
                if clkol(doc, working_field, ivl):
                    indexed_ivl = operations[operation]["fields"][ivl]
                    in_vals[ivl] = glkol(doc, working_field, ivl)
                    ivl_vals[indexed_ivl] = glkol(doc, working_field, ivl) # i am too tired right now to understand what i did here

            table_in_cols = ""
            table_val_cols = ""
            for tincol in in_vals:
                table_in_cols += operations[operation]["fields"][tincol] + ',' # sql injection
                table_val_cols += '%(' + operations[operation]["fields"][tincol] + ')s,' # sql injection
            table_in_cols = table_in_cols[:-1]
            table_val_cols = table_val_cols[:-1]

            postgres_cursor = pdb.cursor()

            print('attempting: ', """INSERT INTO {0} ({1}) VALUES ({2})""".format(table_name, table_in_cols, table_val_cols), ivl_vals)
            postgres_cursor.execute("""INSERT INTO {0} ({1}) VALUES ({2})""".format(table_name, table_in_cols, table_val_cols), ivl_vals)
            pdb.commit()


try:
    db_settings = json.loads(open('dbschmap.json').read())
except Exception as e:
    print("Either the file dbschmap.json could not be found in your working directory, or it doesn't contain valid json.\nDetails:")
    print(e)
    exit(-1)
try:
    mclient = pymongo.MongoClient(db_settings["dbsetup"]["mongo_uri"])
except:
    print("Mongo server is not accessible")
    exit(-1)


for database in db_settings["dbnames"]:
    print("Connecting to {0}...".format(database["output"]))
    postgre_db = con_pql(database["output"])
    if(postgre_db == -1): continue
    print("Connecting to {0}...".format(database["input"]))
    mongo_db = mclient[database["input"]]

    for mtableop in db_settings["operations"]:
        mongo_table = mongo_db[mtableop] # first we get the table we want to work in
        for doc in mongo_table.find(): # then we loop over all the documents
            recursive_exec(doc, db_settings["operations"][mtableop], [], postgre_db)