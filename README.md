# The School of Salamanca – Web Data Factory

## Overview

This is an experimental, proof-of-concept implementation of a web service for 
deriving data in various formats (such as HTML or plain text) from TEI/XML of the 
[School of Salamanca project](http://www.salamanca.school). It is based on Python and 
the [Flask](https://palletsprojects.com/p/flask/) web framework and makes extensive use of 
Python's [lxml library](https://lxml.de/) for processing XML data. 

There were two main objectives in the development of this service: 
1. it should be explored in which way and to what extent the derivation of 
"webdata" (like the above) could be outsourced from the School of 
Salamanca's [main web application](https://www.github.com/digicademy/svsal) and 
implemented as a dedicated (micro)service, and how the overall IT architecture of 
the project could benefit from such a modularization;
2. due to the necessity of processing large and heterogeneous amounts of TEI/XML data, 
the main web application is largely based on rather specific, XML-driven technologies and platforms such as 
XQuery, XSLT, and [eXist-db](http://exist-db.org); re-implementing the 
derivation of webdata in a programming language like Python should shed some light on potential benefits 
and/or disadvantages of refactoring XML-based application logic using a more "general-purpose" 
programming language.

While the svsal-factory has not been fully implemented yet, certain tendencies have become visible during 
its development, especially when comparing it to the currently existing architecture driven by a rather monolithic 
main web application. Possible benefits are
- the decoupling of computing-intensive tasks from the main web application, 
which makes it possible, for instance, to deploy the web service on a 
different server than the one where the main web application is located, thus 
freeing hardware resources for the latter;
- an apparent increase in performance in the processing of TEI datasets, especially 
larger ones; the precise extent of this performance increase 
has not been measured yet, but it seems to be significant at 
times (with the transformation of XML into HTML taking minutes 
rather than hours, for example);
- a relatively light footprint on hardware resources (especially CPU and RAM), 
at least in Flask's testing environment.

A significant downside is the seeming non-availability of production-ready XQuery/XSLT 3.x processors/libraries 
in Python, which leads to an increase in programming complexity, since hitherto available and handy
solutions based on XQuery/XSLT 3.x need to be refactored using XPath or XSLT 1.x, or even pure Python. 
Such a mixing of programming languages and tools makes the code harder to read and, consequently, 
the derivation of webdata more difficult to maintain and adjust in the long run.


## Install and Run (on Linux)

(Please note that the application has been developed and tested only with Python 3.7.x thus far.)

1.) Clone the repo, create a virtual environment, and install basic requirements:

`git clone https://github.com/digicademy/svsal-factory.git`

`cd svsal-factory`

`python3 -m venv venv`

`source venv/bin/activate`

`pip3 install -r requirements.txt`

2.) Set environment variables:

`export FLASK_APP=setup.py`

`export FLASK_ENV=development`

Debug mode (optional): `export FLASK_DEBUG=1`

3.) Run

`flask run`


## Usage

In general, the web service functions in the following way: it consumes a TEI dataset, 
processes it, and puts out a JSON dataset that contains objects for all relevant 
structural units in the TEI document (such as a tei:p or tei:list). 
These JSON object include metadata about their textual units 
as well as HTML and (diplomatic and constituted) plain text versions of the respective text segments. 
(RDF or IIIF data are currently not created by the service, although this could be equally built into the service.) 
Furthermore, the comprehensive JSON dataset contains (bibliographical 
and technical) metadata for the complete work. In general, the resulting 
JSON data are in a format that is supposed to be easily transformable 
into [Distributed Text Services](https://distributed-text-services.github.io/specifications/) JSON objects; 
in fact, some fields (such as `dts:citeDepth` or `dts:dublincore` in the `work_metadata`) are already largely DTS-compliant (as of March 2020).

The services' API offers a "texts" endpoint to which TEI data can be POSTed. 
Since the processing of a (larger) TEI dataset usually is a long-running task, 
the "texts" endpoint works in an asynchronous way: it immediately returns a 202 "Accepted" response
rather than letting the client wait for the processed data, and the response contains a `Location` header 
providing a link to a "tasks" endpoint. The linked task resource 
offers information about the status of the processing if the processing 
has not finished yet, or the complete result data 
once the TEI has been fully processed. Please note that result data will not be
available forever, since the service's internal garbage 
collector will remove it at some point in order to free memory. 

### Example

1.) Get a TEI dataset from the School of Salamanca:

`wget https://id.salamanca.school/texts/W0004?format=tei -O W0004.xml`

2.) POST the TEI data to the "texts" endpoint

`curl -X POST -d @W0004.xml -H "Content-Type: application/xml" localhost:5000/v1/texts/W0004 -v`

Please note: due to an unresolved bug, the web service's REST controller sometimes requires
XML data to be sent twice (as two POST requests) in order to trigger the processing of the data. 
In this case, the `Location` header of the _last_ POST request applies to 3.) and 4.) (see below).

3.) Check the `Location` header of the response, which provides a link to the "tasks" endpoint that will eventually 
provide the result data:

```Content-Type: application/json
...
Location: http://localhost:5000/tasks/c2d190b1498f482ea9a217127a6a2138
...
``` 

4.) Make a GET request to the "tasks" endpoint obtained in 3.):

`curl -X GET http://localhost:5000/tasks/c2d190b1498f482ea9a217127a6a2138`

If the service is still processing, the response will be a simple "still_processing" 
string. When processing has finished,
the complete result data will be returned in the response body.


## Caveats

As mentioned above, this service has thus far been developed mostly as a proof of concept with 
only basic functionality in mind, and it is definitely not ready for production at the moment: 
there is almost no automatic testing, and error handling is very rudimentary, if that. Thus, it should be regarded 
as the prototype of a future web service rather than as a readily usable application. 
