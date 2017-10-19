import os, sys, glob, datetime, argparse, ieo
from osgeo import ogr, osr

# Parse command line arguments
parser = argparse.ArgumentParser('Create ESPA LEDAPS process list for missing scenes.')
parser.add_argument('--path', type = int, help = 'WRS-2 Path')
parser.add_argument('--row', type = int, help = 'WRS-2 Row. If this is specified, then --path must also be specified.')
parser.add_argument('--maxcc', default = 100.0, type = float, help = 'Maximum cloud cover in percent')
parser.add_argument('--startdate', type = str, help = 'Starting date, DD/MM/YYYY')
parser.add_argument('--enddate', type = str, help = 'Ending date, DD/MM/YYYY')
parser.add_argument('--startdoy', type = int, help = 'Starting day of year, 1-366')
parser.add_argument('--enddoy', type = int, help = 'Ending day of year, 1-366. If less than starting day of year then this will be used to span the new year.')
parser.add_argument('--startyear', type = int, help = 'Starting year')
parser.add_argument('--endyear', type = int, help = 'Ending year. If less than starting starting year then these will be swapped.')
parser.add_argument('--landsat', type = int, help = 'Landsat number (4, 5, 7, or 8 only).')
parser.add_argument('--sensor', type = str, help = 'Landsat sensor: TM, ETM, ETM_SLC_OFF, OLI, OLI_TIRS, TIRS')
parser.add_argument('--shp', type = str, default = os.path.join(ieo.catdir, 'WRS2_Ireland_scenes.shp'), help = 'Full path and filename of alternative shapefile.')
parser.add_argument('-o', '--outdir', type = str, default = os.path.join(ieo.catdir, 'LEDAPS_processing_lists'), help = 'Output directory')
parser.add_argument('--ignorelocal', type = bool, default = False, help = 'Ignore presence of local scenes.')
parser.add_argument('--srdir', type = str, default = ieo.srdir, help = 'Local SR scene directory')
parser.add_argument('--usesrdir', type = bool, default = True, help = 'Use local index of scenes rather than shapefile stored data')
parser.add_argument('--allinpath', type = bool, default = True, help = 'Include missing scenes in path, even if they are too cloudy.')
parser.add_argument('--minsunel', type = float, default = 15.0, help = 'Sun elevation beneath which scenes will be ignored.')
parser.add_argument('--separate', type = bool, default = False, help = 'Separate output files for Landsats 4-7 and 8.')
parser.add_argument('--L1G', type = bool, default = False, help = 'Also get L1G and L1GT scenes.')
parser.add_argument('--L1GT', type = bool, default = False, help = 'Also get L1GT scenes but exclude L1G.')
parser.add_argument('--ALL', type = bool, default = False, help = 'Get any scene regardless of processing level.')
args = parser.parse_args()

outdir = args.outdir
infile = args.shp
today = datetime.datetime.today()
todaystr = today.strftime('%Y%m%d-%H%M%S')

localscenelist = []

if args.sensor:
    if 'TM' in args.sensor:
        sensor='LANDSAT_%s'%args.sensor
    elif not ('OLI' in args.sensor or 'TIRS' in args.sensor):
        print('Error: this sensor is not supported. Acceptable sensors are: TM, ETM, ETM_SLC_OFF, OLI, OLI_TIRS, TIRS. Leaving --sensor blank will search for all sensors. Exiting.')
        exit()
    else:
        sensor = args.sensor
else:
    sensor = ''

if not args.path:
    path = 0
else:
    path = args.path
if not args.row:
    row = 0
else:
    row = args.row

if args.startdoy or args.enddoy:
    if not (args.startdoy and args.enddoy):
        print('Error: if used, both --startdoy and --enddoy must be defined. Exiting.')
        exit()
    
if args.startdate:
    startdate = datetime.datetime.strptime(args.startdate,'%Y/%m/%d')
if args.enddate:
    enddate = datetime.datetime.strptime(args.enddate,'%Y/%m/%d')

if args.usesrdir:
    dirs = [args.srdir, os.path.join(args.srdir,'L1G')]
    for d in dirs:
        flist = glob.glob(os.path.join(d,'L*_ref_ITM.dat'))
        if len(flist) > 0:
            for f in flist:
                if os.path.isfile(f):
                    localscenelist.append(os.path.basename(f)[:21])

proclevels = ['L1T']
if args.L1G:
    proclevels = ['L1T', 'L1GT', 'L1Gt', 'L1G']
elif args.L1GT:
    proclevels = ['L1T', 'L1GT', 'L1Gt']
elif args.ALL:
    proclevels = ['L1T', 'L1GT', 'L1Gt', 'L1G', 'PR']

def getscenedata(layer, localscenelist):
    scenedata = {}
    for feature in layer:
        sceneID = feature.GetField("sceneID")
        includescene = True
        sunEl = feature.GetField("sunEl")
        sensor = feature.GetField("sensor")
        acqDate = datetime.datetime.strptime(feature.GetField("acqDate"),'%Y/%m/%d')
        datestr = acqDate.strftime('%Y%j')
        proclevel = feature.GetField("DT_L1")
        if sceneID[2:3] == '8' and ((datestr in L8exclude) or (sensor != 'OLI_TIRS')):
            includescene = False
        if sceneID[2:3] == '7' and datestr in L7exclude:
            includescene = False
        if includescene and sunEl >= args.minsunel:
            LEDAPS = feature.GetField("LEDAPS")
            scenedata[sceneID] = [acqDate, feature.GetField("path"), feature.GetField("row"), sensor, feature.GetField("CCFull"), sunEl, LEDAPS, proclevel]
            if LEDAPS and not args.usesrdir:
                if os.path.isfile(LEDAPS):
                    localscenelist.append(os.path.basename(LEDAPS))
    return scenedata, localscenelist

def scenesearch(scenedata, sceneID):
    keys = scenedata.keys()
    scout = []
    path = scenedata[sceneID][1]
    if path == 207 or path == 208:
        r = 21
    else:
        r = 22
    if scenedata[sceneID][6]:
        if os.path.exists(scenedata[sceneID][6]):
            row = scenedata[sceneID][2]
            while r < 25:
                if r != row:
                    s = '%s%03d%s' % (sceneID[:6],r,sceneID[9:16])
                    sc = [y for y in keys if s in y]
                    for s in sc:
                        if not s in scout:
                            scout.append(s)
                r += 1
    return scout    

def findmissing(l8, l47, scenedata, localscenelist):
    keys = scenedata.keys()
    for sceneID in keys:
        if not sceneID in localscenelist:
            if sceneID[2:3] == '8' and not any(sceneID in l8[key] for key in l8.keys()):
                print('Adding %s to Landsat 8 processing list.'%sceneID)
                if not sceneID[9:16] in l8.keys():
                    l8[sceneID[9:16]] = [sceneID]
                else:
                    l8[sceneID[9:16]].append(sceneID)
            elif sceneID[2:3] != '8' and not any(sceneID in l47[key] for key in l47.keys()):
                print('Adding %s to Landsat 4-7 processing list.'%sceneID)
                if not sceneID[9:16] in l47.keys():
                    l47[sceneID[9:16]] = [sceneID]
                else:
                    l47[sceneID[9:16]].append(sceneID) 
#        sc = scenesearch(scenedata, sceneID)
#        if len(sc) > 0:
#            for s in sc:
#                if not scenedata[s][6]:
#                    if s[2:3] == '8' and not s in l8:
#                        print('Adding %s to Landsat 8 processing list.'%s)
#                        l8.append(s)
#                    elif not s in l47:
#                        print('Adding %s to Landsat 4-7 processing list.'%s)
#                        l47.append(s) 
    return l8, l47

def populatelists(l8, l47, scenedata, localscenelist):
    for sceneID in scenedata.keys():
        acqDate = scenedata[sceneID][0]
        path = scenedata[sceneID][1]
        row = scenedata[sceneID][2]
        scenesensor = scenedata[sceneID][3]
        cc = scenedata[sceneID][4]
        sunEl = scenedata[sceneID][5]
        SR = scenedata[sceneID][6]
        proclevel = scenedata[sceneID][7]
        
        if (not sceneID in localscenelist or args.ignorelocal) and cc <= args.maxcc and sunEl >= args.minsunel and proclevel in proclevels: # Only run this for scenes that aren't present on disk or if we choose to ignore local copies.
        # if (feature.GetField("LEDAPS") == None or args.ignorelocal) and feature.GetField("CCFull") <= args.maxcc and feature.GetField("sunEl") >= args.minsunel:
            # sceneID = feature.GetField("sceneID")
            if args.landsat:
                if args.landsat != int(sceneID[2:3]):
                    continue
            if args.path:
                if args.path != path:
                    continue
                # else:
                #     print(path)
            if args.row:
                if args.row != row:
                    continue
                # else:
                #     print(row)
            if args.sensor: 
                if sensor != scenesensor:
                    continue
            
            year = int(sceneID[9:13])
            doy = int(sceneID[13:16])    
            if args.startyear or args.endyear:
                if args.startyear > args.endyear:
                    endyear = args.startyear
                    startyear = args.endyear
                else: 
                    endyear = args.endyear
                    startyear = args.startyear
                if year < startyear or year > endyear:
                    continue
            if args.startdoy and args.enddoy:
                if startdoy < enddoy:
                    if doy < startdoy or doy > enddoy:
                        continue
                else:
                    if args.startyear: 
                        if year == startyear and doy < startdoy:
                            continue
                    if args.endyear:
                        if year == endyear and doy > enddoy:
                            continue
                    if doy > endday and doy < startday:
                        continue
            
            if args.startdate or args.enddate:
                acqdate = datetime.datetime.strptime(feature.GetField("acqDate"),'%Y/%m/%d')
                if args.startdate:
                    if startdate > acqdate:
                        continue
                if args.enddate:
                    if enddate < acqdate:
                        continue
            
            # cc = feature.GetField("CCFull")
            
            print('Scene %s, cloud cover of %s percent, added to list.'%(sceneID,cc))
            if not sceneID[9:16] in L7exclude and not sceneID[2:3] == '8': #(scenesensor == 'LANDSAT_TM' or scenesensor == 'LANDSAT_ETM' or 'LANDSAT_ETM_SLC_OFF') and 
                if not sceneID[9:16] in l47.keys():
                    l47[sceneID[9:16]] = [sceneID]
                elif not sceneID in l47[sceneID[9:16]]:
                    l47[sceneID[9:16]].append(sceneID)
                if args.allinpath:
                    sc = scenesearch(scenedata, sceneID)
                    if len(sc) > 0:
                        for s in sc:
                            if not s in l47[sceneID[9:16]]:
                                print('Also adding scene %s to the processing list.'%sceneID)
                                l47[sceneID[9:16]].append(s)
                
    #        elif scenesensor=='LANDSAT_ETM':
    #            l7.append(sceneID)
    #        elif scenesensor=='LANDSAT_ETM_SLC_OFF' and not sceneID[9:16] in L7exclude:
    #            l7slcoff.append(sceneID)
            elif sceneID[2:3] == '8' and not sceneID[9:16] in L8exclude:
                if not sceneID[9:16] in l8.keys():
                    l8[sceneID[9:16]] = [sceneID]
                elif not sceneID in l8[sceneID[9:16]]:
                    l8[sceneID[9:16]].append(sceneID)
                if args.allinpath:
                    sc = scenesearch(scenedata, sceneID)
                    if len(sc) > 0:
                        for s in sc:
                            if not s in l8[sceneID[9:16]]:
                                print('Also adding scene %s to the processing list.'%sceneID)
                                l8[sceneID[9:16]].append(s)
    return l8,l47

# Exclusion of problematic dates:

L8exclude = []
for i in range(21):
    L8exclude.append('2015%03d'%(30 + i))
for i in range(9):
    L8exclude.append('2016%03d'%(50 + i))

L7exclude = []
for i in range(15):
    L7exclude.append('2016%03d'%(151 + i))

# Set various other variables


print('Opening %s'%infile)
if args.path and args.row:
    print('Searching for scenes from WRS-2 Path %d, Row %d, with a maximum cloud cover of %0.1f%%.'%(args.path, args.row, args.maxcc))
driver = ogr.GetDriverByName("ESRI Shapefile")
dataSource = driver.Open(infile,0)
layer = dataSource.GetLayer()
layer_defn = layer.GetLayerDefn()
field_names = [layer_defn.GetFieldDefn(i).GetName() for i in range(layer_defn.GetFieldCount())]
scenedata, localscenelist = getscenedata(layer, localscenelist)
    

l8 = {}
l47 = {}
l7slcoff = {}
l5 = {}

l8, l47 = populatelists(l8, l47, scenedata, localscenelist)

if args.allinpath:
    print('Now searching for missing scenes from same paths and dates of locally stored scenes.')
    l8, l47 = findmissing(l8, l47, scenedata, localscenelist)


if args.separate:
    if len(l8.keys())>0:
        i = 0
        outfile = os.path.join(outdir,'LEDAPS_L8_list%s.txt'%todaystr)
        print('Writing output to: %s'%outfile)
        keylist = list(l8.keys())
        keylist.sort()
        with open(outfile,'w') as output:
            for key in keylist:
                for scene in l8[key]:
                    if scene.startswith('LC8'): # Excludes Landsat 8 scenes that do not contain both OLI and TIRS data 
                        output.write('%s\n'%scene)
                        i += 1
        print('{} scenes for ESPA to process.'.format(i))
    
    if len(l47.keys())>0:
        i = 0
        outfile = os.path.join(outdir,'LEDAPS_L47_list%s.txt'%todaystr)
        print('Writing output to: %s'%outfile)
        keylist = list(l47.keys())
        keylist.sort()
        with open(outfile,'w') as output:
            for key in keylist:
                for scene in l47[key]:
                    if key[2:3] != '8':
                        output.write('%s\n'%scene)
                        i += 1
        print('{} scenes for ESPA to process.'.format(i))
else:
    i = 0
    outfile = os.path.join(outdir,'LEDAPS_list%s.txt'%todaystr)
    print('Writing output to: %s'%outfile)
    with open(outfile,'w') as output:
        for d in [l47, l8]:
            if len(d.keys()) > 0:
                keylist = list(d.keys())
                keylist.sort()
                for key in keylist:
                    for scene in d[key]:
                        output.write('%s\n'%scene)
                        i += 1
    print('{} scenes for ESPA to process.'.format(i))
                
#        if len(l7)>0:
#            for scene in l7:
#                output.write('%s\n'%scene)
#        if len(l5)>0:
#            for scene in l5:
#                output.write('%s\n'%scene)

print('Processing complete.')