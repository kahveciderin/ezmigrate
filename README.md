# ezmigrate
Migration tool for migrating from MongoDB to PostgreSQL


"easy" as in "easy for *you* to migrate", not as in "easy for **me** to code".




## Usage:

Create a .json file in your working directory, and add the following JSON structure in it:
```
{
    "dbsetup": {
        "username": "<postgres username>",
        "password": "<postgres password>",
        "host": "<postgres host>",
        "port": "<postgres port>",
        "mongo_uri": "mongodb://<mongo uri (without database name)>",
        "thread_count_per_operation_per_database": <count>
    },
    "dbnames": [
        {
            "input": "<mongo db name>",
            "output": "<postgres db name>"
        }
    ],
    "operations": {
    }
}
```

**Warning:** `thread_count_per_operation_per_database` is the number of threads the program will spawn PER ROOT LEVEL SCOPE PER DATABASE. If you have 3 root level scopes and 6 databases, the threads spawned will be 3 * 6 * thread_count_per_operation_per_database.


**Note:** In order for this to work, there needs to be an `id` field in every table in PostgreSQL that is set to SERIAL and is the PRIMARY KEY.

You can add as many database names as you want in the `dbnames` array.

Create an object inside `operations` that is the same name as the collection in MongoDB.

Inside that object, you will write *scopes*.

A scope is an object or a field in the MongoDB object that needs to be further processed and/or inserted into PostgreSQL. Every scope starts with **$** and is a JSON object. There can be directives or another scope inside a scope.

Available directives:

  * `insert`
  * `for`

`for` directive takes an array of objects that contain operations/scopes/other directives. It then runs every object in that array for each object in the previously selected array in MongoDB. It will also return the current index in the loop as `$$lindex-n` where *n* is the number of for loops you want to go in.

`insert` directive takes an object with specifications telling it where to insert.

Available specifications are:  
`name`: required  
   * Name of the table as string.  
`fields`: required  
   * An object with source: destination pairs.  
   * Source can be one of:  
        - An object in MongoDB from the current scope:  
            ```"source": "destination"```  
            ```"source.elem": "destination"```  
        - An object in MongoDB from a parent scope:  
            ```"#1": "destination"``` will bring the parent element from a scope before.  
            ```"#2": "destination"``` will bring the parent element from 2 scopes before.  
        - A variable:  
            `$$lindex-n` from **for**  
            `$$psid` from **insert** -> **after**  
        - An inline operation (Note that this is different from normal operations):  
            `$push-source` will push the source element from the current scope to an array  
`options`: optional  
  * inside `options`, you can set a few options:  
      * `unique` tells the database that this permutation of fields needs to be unique in order to insert into the database. If not, an empty UPDATE call will be executed, resulting in no change in the database.  
`after`: optional  
  * this is an object, similar to the root level `operations`, that will execute the contents, but it will do it after the insert operation is done. Also, the `id` field will be returned as variable `$$psid`.  

