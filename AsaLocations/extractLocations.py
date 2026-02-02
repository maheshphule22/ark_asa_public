import json

def getJsonData():
    with open('AsaLocations.json') as json_file:
        data = json.load(json_file)
    return data

def find_values(json_data, keys_to_find):
    if isinstance(json_data, dict):
        keys_present = all(key in json_data for key in keys_to_find)
        if keys_present:
            yield {key: json_data[key] for key in keys_to_find}
        else:
            for value in json_data.values():
                yield from find_values(value, keys_to_find)
    elif isinstance(json_data, list):
        for item in json_data:
            yield from find_values(item, keys_to_find)

def get_location_list():
    jsonData = getJsonData()
    extracted_data = list(find_values(jsonData, ['label', 'desc']))
    print(f'Got total {len(extracted_data)} locations')
    return extracted_data

def extractLocations():
    location_list = get_location_list()

    for location in location_list:
        
        # process 'lable' from location_list
        # take data only before <span> tag
        location['label'] = location['label'].split('<span')[0]
        # remove before and after spaces
        location['label'] = location['label'].strip()

        # remove 'Note' and 'Record' from label
        if 'Note ' in location['label']:
           location['label'] = location['label'].replace('Note ', '')
        if 'Record ' in location['label']:
          location['label'] = location['label'].replace('Record ', '')
         
        # replace space with underscore
        location['label'] = location['label'].replace(' ', '_')
        
        # process 'desc' from location_list
        # get data from <code> tag
        if '</code>' in location['desc'].lower():
            location['desc'] = location['desc'].split('</code>')[0]
            location['desc'] = location['desc'].split('<code>')[1]
        if 'cheat spi ' in location['desc'].lower():
            location['desc'] = location['desc'].split('cheat spi ')[1]        
    
    # print location_list
    for location in location_list:
        print(location)

    # write location_list to csv file
    with open('AsaLocations.csv', 'w') as f:
        for location in location_list:
            f.write("%s,%s\n"%(location['label'],location['desc']))

extractLocations()