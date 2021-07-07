from multiprocessing import Process
import psycopg2
import pymongo
import json
import time
import copy



THREAD_COUNT_PER_OPERATION_PER_DATABASE = 16





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

def glkol(obj, namespace, last, did = -1):
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
        elif last.startswith('$$docn'):
            return did[0]
        elif last.startswith('$$psid'):
            return did[1]
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

def recursive_exec(document_id, doc, operations, wf, pdb):
    pdb_name = copy.copy(pdb)
    pdb = con_pql(pdb) # immediately restore postgre database
    for operation in operations:
        working_field = wf
        if(operation[0] == '$'): # this is a field name in the current document
            working_field.append(operation[1:])
            recursive_exec(document_id, doc, copy.copy(operations[operation]), copy.copy(working_field), pdb_name)
        elif(operation == "for"):
            for_index = 0
            for lot_for in get_list_keyed_obj(doc, working_field):
                new_wf = copy.copy(working_field)
                new_wf.append(copy.copy(for_index))
                for ops in operations[operation]:
                    recursive_exec(document_id, doc, copy.copy(ops), copy.copy(new_wf), pdb_name)
                for_index += 1
        elif(operation == "insert"):
            table_name = operations[operation]["name"]
            in_vals = {}
            ivl_vals = {}
            hiv_vals = ""
            for ivl in operations[operation]["fields"]:
                if clkol(doc, working_field, ivl):
                    indexed_ivl = operations[operation]["fields"][ivl]
                    in_vals[ivl] = glkol(doc, working_field, ivl, did=document_id)
                    ivl_vals[indexed_ivl] = glkol(doc, working_field, ivl, did=document_id) # i am too tired right now to understand what i did here
                hiv_vals += ivl + ','
            hiv_vals = hiv_vals[:-1]

            table_in_cols = ""
            table_val_cols = ""
            for tincol in in_vals:
                table_in_cols += operations[operation]["fields"][tincol] + ',' # sql injection
                table_val_cols += '%(' + operations[operation]["fields"][tincol] + ')s,' # sql injection
            table_in_cols = table_in_cols[:-1]
            table_val_cols = table_val_cols[:-1]

            postgres_cursor = pdb.cursor()
            

            sql_query = """INSERT INTO {0} ({1}) VALUES ({2}) RETURNING id""".format(table_name, table_in_cols, table_val_cols)
            if "options" in operations[operation]:
                if "unique" in operations[operation]["options"]:
                    sql_query = """INSERT INTO {0} ({1})
                    VALUES ({2}) ON CONFLICT ({4})
                    DO UPDATE SET {3}=EXCLUDED.{3} RETURNING id""".format(table_name, table_in_cols, table_val_cols, list(ivl_vals)[0], hiv_vals)
            print('attempting: ', sql_query, ivl_vals)
            postgres_cursor.execute(sql_query, ivl_vals)
            pdb.commit()
            apparent_id = postgres_cursor.fetchone()[0]
            if "after" in operations[operation]:
                aid = copy.copy(document_id)
                aid.append(apparent_id)
                recursive_exec(aid, doc, copy.copy(operations[operation]["after"]), copy.copy(working_field), pdb_name) # aid[0] is document id, aid[1] is id of the last inserted


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
    postgre_db = database["output"] # we pass the name here because this will be reconnected every time while multiprocessing
    if(postgre_db == -1): continue
    print("Connecting to {0}...".format(database["input"]))
    mongo_db = mclient[database["input"]]

    for mtableop in db_settings["operations"]:
        mongo_table = mongo_db[mtableop] # first we get the table we want to work in
        document_id = 0
        thread_id = 0
        mongo_docs = mongo_table.find()
        jobs = []
        for doc in mongo_docs: # then we loop over all the documents
            # recursive_exec([document_id], doc, copy.copy(db_settings["operations"][mtableop]), [], postgre_db)
            # mongo_thread = threading.Thread(target=recursive_exec, args=([document_id], doc, copy.copy(db_settings["operations"][mtableop]), [], postgre_db))
            # mongo_thread.start()
            mongo_thread = Process(target=recursive_exec, args=([document_id], doc, copy.copy(db_settings["operations"][mtableop]), [], postgre_db))
            mongo_thread.start()
            print("THREAD START")
            jobs.append(mongo_thread)
            document_id += 1
            thread_id += 1
            if(thread_id % THREAD_COUNT_PER_OPERATION_PER_DATABASE == 0): # thread count per database per operation
                thread_id = 0
                while len(jobs) > 0:
                    jobs = [job for job in jobs if job.is_alive()]
                    time.sleep(1)