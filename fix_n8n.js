const fs = require('fs');

const data = JSON.parse(fs.readFileSync('n8n.json', 'utf8'));

// Delete stray text parameters from agents to revert to default behavior
data.nodes.forEach(n => {
  if (n.name === 'MCqueen' || n.name === 'Analista') {
    delete n.parameters.text;
  }
});

// Create Code nodes
const codeMcQueen = {
  "parameters": {
    "jsCode": "for (const item of $input.all()) {\n  item.json.chatInput = \"Modelo do carro para analisar: \" + item.json.body.carModel;\n}\nreturn $input.all();"
  },
  "id": "code-mcqueen",
  "name": "Map Input McQueen",
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "position": [-16, -232]
};

const codeAnalista = {
  "parameters": {
    "jsCode": "for (const item of $input.all()) {\n  item.json.chatInput = \"Gere os dados TCO para o modelo: \" + item.json.body.carModel;\n}\nreturn $input.all();"
  },
  "id": "code-analista",
  "name": "Map Input Analista",
  "type": "n8n-nodes-base.code",
  "typeVersion": 2,
  "position": [-80, 288]
};

data.nodes.push(codeMcQueen, codeAnalista);

// Rewire Webhook1 -> Code -> MCqueen
data.connections["Webhook1"] = {
  "main": [ [ { "node": "Map Input McQueen", "type": "main", "index": 0 } ] ]
};
data.connections["Map Input McQueen"] = {
  "main": [ [ { "node": "MCqueen", "type": "main", "index": 0 } ] ]
};

// Rewire Webhook -> Code -> Analista
data.connections["Webhook"] = {
  "main": [ [ { "node": "Map Input Analista", "type": "main", "index": 0 } ] ]
};
data.connections["Map Input Analista"] = {
  "main": [ [ { "node": "Analista", "type": "main", "index": 0 } ] ]
};

// Remove the old When chat message received connection to Analista (we only want Webhook)
if (data.connections["When chat message received"]) {
    delete data.connections["When chat message received"];
}

fs.writeFileSync('n8n.json', JSON.stringify(data, null, 2));
console.log('n8n.json updated successfully.');
