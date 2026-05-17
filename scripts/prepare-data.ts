import fs from 'fs';
import path from 'path';
import AdmZip from 'adm-zip';
import Papa from 'papaparse';
import * as shapefile from 'shapefile';

const workspace = path.resolve('.');
const zipFile = path.join(workspace, 'VistaBallotAreas.zip');
const csvFile = path.join(workspace, 'utah_county_estimated_votes_nlcd_pooled.csv');
const outputFile = path.join(workspace, 'public', 'data', 'utah-votes.geojson');
const tempDir = path.join(workspace, '.tmp-shapefile');

const yearMap: Record<string, string> = {
  '16': '2016',
  '18': '2018',
  '20': '2020',
  '22': '2022',
  '24': '2024',
};

const raceMap: Record<string, string> = {
  PRE: 'President',
  USS: 'U.S. Senate',
  GOV: 'Governor',
  AUD: 'Auditor',
  TRE: 'Treasurer',
  ATG: 'Attorney General',
  ATM: 'Attorney General',
  OTH: 'Other',
};

function parseNumber(value: unknown) {
  if (value === null || value === undefined) return 0;
  const numeric = Number(String(value).replace(/,/g, '').trim());
  return Number.isFinite(numeric) ? numeric : 0;
}

function createSummary(row: Record<string, string>) {
  const yearTotals: Record<string, number> = {
    '2016': 0,
    '2018': 0,
    '2020': 0,
    '2022': 0,
    '2024': 0,
  };
  const raceTotals: Record<string, number> = {
    'All races': 0,
    President: 0,
    'U.S. Senate': 0,
    Governor: 0,
    Auditor: 0,
    Treasurer: 0,
    'Attorney General': 0,
    Other: 0,
  };

  for (const key of Object.keys(row)) {
    if (!key.startsWith('G') || key.length < 4) continue;
    const yearCode = key.slice(1, 3);
    const year = yearMap[yearCode];
    if (!year) continue;

    const value = parseNumber(row[key]);
    yearTotals[year] += value;
    raceTotals['All races'] += value;

    const raceCode = key.slice(3, 6).toUpperCase();
    const raceName = raceMap[raceCode] ?? raceCode;
    raceTotals[raceName] = (raceTotals[raceName] ?? 0) + value;
  }

  return { yearTotals, raceTotals };
}

function getFeatureVistaId(properties: Record<string, unknown>) {
  const raw =
    (properties['VistaID'] as string) ||
    (properties['VISTAID'] as string) ||
    (properties['vistaid'] as string) ||
    (properties['vistasid'] as string) ||
    (properties['VistaId'] as string);
  return typeof raw === 'string' ? raw.trim() : String(raw ?? '');
}

async function main() {
  console.log('Preparing Utah election GeoJSON data...');

  if (!fs.existsSync(zipFile)) {
    throw new Error(`Missing ZIP file at ${zipFile}`);
  }

  if (!fs.existsSync(csvFile)) {
    throw new Error(`Missing CSV file at ${csvFile}`);
  }

  if (fs.existsSync(tempDir)) {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
  fs.mkdirSync(tempDir, { recursive: true });

  console.log('Extracting shapefile from ZIP...');
  const zip = new AdmZip(zipFile);
  zip.extractAllTo(tempDir, true);

  const shpPath = path.join(tempDir, 'VistaBallotAreas.shp');
  const dbfPath = path.join(tempDir, 'VistaBallotAreas.dbf');

  if (!fs.existsSync(shpPath) || !fs.existsSync(dbfPath)) {
    throw new Error('Expected shapefile components were not found in the ZIP archive.');
  }

  console.log('Reading CSV vote data...');
  const csvText = fs.readFileSync(csvFile, 'utf8');
  const parsed = Papa.parse<Record<string, string>>(csvText, {
    header: true,
    skipEmptyLines: true,
  });

  const csvByVistaId = new Map<string, Record<string, string>>();
  for (const row of parsed.data) {
    const vistaId = String(row['VistaID'] || row['vistaid'] || row['VISTAID'] || '').trim();
    if (vistaId) {
      csvByVistaId.set(vistaId, row);
    }
  }

  console.log(`Loaded ${csvByVistaId.size} vote records.`);

  const source = await shapefile.open(shpPath, dbfPath);
  const features = [];
  let result = await source.read();
  while (!result.done) {
    const feature = result.value as any;
    const vistaId = getFeatureVistaId(feature.properties || {});
    const csvRow = csvByVistaId.get(vistaId);

    const voteStats = csvRow ? createSummary(csvRow) : {
      yearTotals: {
        '2016': 0,
        '2018': 0,
        '2020': 0,
        '2022': 0,
        '2024': 0,
      },
      raceTotals: {
        'All races': 0,
        President: 0,
        'U.S. Senate': 0,
        Governor: 0,
        Auditor: 0,
        Treasurer: 0,
        'Attorney General': 0,
        Other: 0,
      },
    };

    feature.properties = {
      ...feature.properties,
      displayName: vistaId ? `Vista ${vistaId}` : 'Unknown area',
      VistaID: vistaId,
      CountyID: feature.properties?.CountyID ?? '',
      voteStats,
    };

    features.push(feature);
    result = await source.read();
  }

  const geoJson = {
    type: 'FeatureCollection',
    features,
  };

  fs.mkdirSync(path.dirname(outputFile), { recursive: true });
  fs.writeFileSync(outputFile, JSON.stringify(geoJson, null, 2), 'utf8');

  console.log(`Created GeoJSON with ${features.length} features at ${outputFile}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
