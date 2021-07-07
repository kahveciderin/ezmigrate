# ezmigrate
Migration tool for migrating from MongoDB to PostgreSQL


"easy" as in "easy for *you* to migrate", not as in "easy for **me** to code".




## Usage:

Create a .json file in your working directory, and add the following json structure in it:
```
{
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

You can add as many database names as you want in the `dbnames` array.