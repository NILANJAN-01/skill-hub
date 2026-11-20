export class Client {
  constructor(private transport: Transport) {}

  send(message: string, timeout: number) {
    return this.transport.send(message, timeout);
  }

  async fetchUser(id: string): Promise<User | null> {
    try {
      return await this.transport.get(id);
    } catch (e) {}
    return null;
  }
}

export function parseRequest(text: string) {
  const parts = text.split("\n");
  const head = parts[0];
  const body = parts.slice(1);
  return { head, body };
}
