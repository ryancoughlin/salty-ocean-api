const fetch = require("node-fetch");
const _ = require("lodash");
const fs = require("fs");

const stations = [
  "8736897",
  "8735180",
  "8734673",
  "8736163",
  "8737048",
  "8737005",
  "8732828",
  "9461380",
  "9457804",
  "9455920",
  "9461710",
  "9490096",
  "9454050",
  "9452634",
  "9452210",
  "9450460",
  "9459881",
  "9457292",
  "9455760",
  "9462450",
  "9468756",
  "9451054",
  "9463502",
  "9497645",
  "9491094",
  "9459450",
  "9455500",
  "9455090",
  "9451600",
  "9452400",
  "9468333",
  "9462620",
  "9454240",
  "9464212",
  "9453220",
  "2695535",
  "2695540",
  "9414750",
  "9410647",
  "9416841",
  "9419750",
  "9415141",
  "9410230",
  "9410691",
  "9410690161",
  "9410666400",
  "9410670",
  "9410665",
  "9410692",
  "9410660",
  "9415102",
  "9413450",
  "9418767",
  "941477634",
  "941479738",
  "941476367",
  "9414769",
  "9411406",
  "941429617",
  "9415115",
  "9414847",
  "9415020",
  "9415144",
  "9412110",
  "9414523",
  "9414863",
  "9410170",
  "94143111",
  "9414290",
  "9411340",
  "9410840",
  "9410172",
  "9415118",
  "9759412",
  "9757809",
  "9761115",
  "9757112",
  "9751639",
  "9751364",
  "9752235",
  "9752695",
  "9753216",
  "9752619",
  "9751381",
  "9751401",
  "9759110",
  "9759394",
  "9759938",
  "9755371",
  "9754228",
  "8467150",
  "8465705",
  "8461490",
  "8555889",
  "8551762",
  "8557380",
  "8551910",
  "8594900",
  "8728690",
  "8726669223",
  "8720233",
  "8727520",
  "8726724",
  "8720219",
  "8726679",
  "8720030",
  "8725520",
  "8720357295",
  "8720245",
  "8724580",
  "8722670",
  "8720228",
  "8720218",
  "8726667",
  "8726412",
  "8725110",
  "8720215",
  "8726607",
  "8729210",
  "8729108",
  "8729840",
  "8726384",
  "8720625",
  "8720503",
  "8726673",
  "8726520",
  "87266942",
  "8721604",
  "8723970",
  "8723214",
  "8670870",
  "9063020",
  "9063063",
  "9063038",
  "9063053",
  "9063079",
  "9063028",
  "9063085",
  "9075065",
  "9075099",
  "9075014",
  "9075080",
  "9087044",
  "9087031",
  "9087069",
  "9087023",
  "9087088",
  "9087096",
  "9052030",
  "9052058",
  "9099064",
  "9099090",
  "9099018",
  "9099004",
  "9063012",
  "9014070",
  "9014098",
  "9014090",
  "8311062",
  "8311030",
  "9076033",
  "9076024",
  "9076070",
  "9076027",
  "1617760",
  "1612340",
  "1615680",
  "1617433",
  "1612480",
  "1611400",
  "8764401",
  "8764044",
  "8767961",
  "8768094",
  "8761955",
  "8764314",
  "8762484",
  "8766072",
  "8761724",
  "8764227",
  "8767816",
  "8761927",
  "8760922",
  "8760721",
  "8761305",
  "87624821",
  "8413320",
  "8411060",
  "8410140",
  "8418150",
  "8419317",
  "8575512",
  "8574680",
  "8571421",
  "8571892",
  "8575437",
  "8573927",
  "8577018",
  "8574729",
  "8574727",
  "8574728",
  "8570283",
  "8578240",
  "8577330",
  "8573364",
  "8447387",
  "8443970",
  "8447412",
  "8447386",
  "8449130",
  "8447930",
  "8747437",
  "8741501",
  "8741041",
  "8740166",
  "8744707",
  "8741533",
  "8741003",
  "8741094",
  "8534720",
  "8539094",
  "8536110",
  "8530973",
  "8531680",
  "8537121",
  "8519483",
  "8516945",
  "8519532",
  "8510560",
  "8518750",
  "8656483",
  "8651370",
  "8652587",
  "8654467",
  "8658120",
  "8658163",
  "9439040",
  "9432780",
  "9437540",
  "9431647",
  "9435380",
  "1630000",
  "1820000",
  "1631428",
  "1770000",
  "1619910",
  "1890000",
  "8546252",
  "8540433",
  "8548989",
  "8545240",
  "8452944",
  "8452660",
  "8452951",
  "8453662",
  "8454000",
  "8454049",
  "8452314",
  "8665530",
  "8661070",
  "8774230",
  "8775241",
  "8776604",
  "8775870",
  "8774513",
  "8771013",
  "8772447",
  "8771341",
  "877145021",
  "8771486",
  "8770808",
  "8770733",
  "8770777",
  "8773767",
  "8773146",
  "8770613",
  "8775244",
  "8775792",
  "8775237",
  "8770475",
  "8775283",
  "8779770",
  "8773259",
  "8778490",
  "8773701",
  "8779280",
  "8777812",
  "8774770",
  "8770971",
  "8776139",
  "8779749",
  "8770570",
  "8771972",
  "8772985",
  "8773037",
  "8779748",
  "8770822",
  "8775296",
  "8638999",
  "8638863",
  "8638901",
  "8635027",
  "8638511",
  "8632200",
  "8635750",
  "8639348",
  "8632837",
  "8638610",
  "8638595",
  "8631044",
  "8638614",
  "8637611",
  "8637689",
  "9449419",
  "9449424",
  "9449880",
  "9442396",
  "9440422",
  "9443090",
  "9444090",
  "9444900",
  "9447130",
  "9446482",
  "9446484",
  "9440910",
  "9441102"
];

var stationInfo = [];
var counter = 0;

_.forEach(stations, (station, index) => {
  fetch(
    "http://tidesandcurrents.noaa.gov/api/datagetter?station=" +
      station +
      "&datum=mllw&format=json&date=today&range=24&time_zone=lst&units=english&product=water_temperature&interval=h"
  )
    .then(response => response.json())
    .then(json => {
      if (json.metadata) {
        const metadata = json.metadata;
        const station = {
          name: metadata.name,
          stationId: metadata.id,
          location: {
            type: "Point",
            coordinates: [metadata.lon, metadata.lat]
          }
        };

        stationInfo.push(station);
        counter++;

        if (counter == stationInfo.length) {
          fs.writeFile(
            "./enhancedStation.json",
            JSON.stringify(stationInfo),
            function(err) {}
          );
        }
      } else {
        console.log("Invalid station ID, skipping...", station);
      }
    })
    .catch(error => {
      console.log(error);
    });
});
