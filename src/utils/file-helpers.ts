import fs from 'fs/promises';
import path from 'path';

// Check if a file exists
export async function fileExists(filePath: string): Promise<boolean> {
  try {
    await fs.access(filePath, fs.constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

// Create directory if it doesn't exist
export async function ensureDirectory(dirPath: string): Promise<void> {
  try {
    await fs.mkdir(dirPath, { recursive: true });
  } catch (error) {
    console.error(`Error creating directory ${dirPath}:`, error);
    throw error;
  }
}

// Read and parse JSON file
export async function readJsonFile<T>(filePath: string, defaultValue: T): Promise<T> {
  try {
    if (await fileExists(filePath)) {
      const content = await fs.readFile(filePath, 'utf-8');
      return JSON.parse(content) as T;
    }
    return defaultValue;
  } catch (error) {
    console.error(`Error reading JSON file ${filePath}:`, error);
    return defaultValue;
  }
}

// Write data to JSON file
export async function writeJsonFile<T>(filePath: string, data: T): Promise<void> {
  try {
    await ensureDirectory(path.dirname(filePath));
    await fs.writeFile(filePath, JSON.stringify(data, null, 2));
  } catch (error) {
    console.error(`Error writing JSON file ${filePath}:`, error);
    throw error;
  }
}

// List files in a directory with optional extension filter
export async function listFiles(dirPath: string, extension?: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(dirPath, { withFileTypes: true });
    const files = entries
      .filter(entry => entry.isFile() && (!extension || entry.name.endsWith(extension)))
      .map(entry => path.join(dirPath, entry.name));
    
    return files;
  } catch (error) {
    console.error(`Error listing files in ${dirPath}:`, error);
    return [];
  }
}