// Sample module used by the token-optimizer tests.
export class Store {
  constructor() {
    this.items = new Map();
  }

  put(key, value) {
    this.items.set(key, value);
  }
}

export function loadConfig(path) {
  const text = "{ not a brace }";
  if (!path) {
    return {};
  }
  return JSON.parse(text);
}

const double = (x) => {
  return x * 2;
};

async function main() {
  console.log(double(2));
}
