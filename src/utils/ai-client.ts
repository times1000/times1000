import dotenv from 'dotenv';
import OpenAI from 'openai';
import * as llm from '../services/llm';

dotenv.config();

// Initialize OpenAI client for direct access if needed
export const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// Helper function to chat with AI using a specific system prompt
export async function chatWithAI(
  messages: llm.LLMMessage[],
  model: string = 'gpt-4o',
  temperature: number = 0.7,
  maxTokens: number = 1000,
  context: { agentId?: string; planId?: string } = {}
): Promise<string> {
  try {
    // Call the abstracted LLM service
    const response = await llm.chatCompletion(
      messages,
      {
        model,
        temperature,
        maxTokens
      },
      {
        operation: 'chat',
        agentId: context.agentId,
        planId: context.planId
      }
    );
    
    return response.content;
  } catch (error: any) {
    throw new Error(`Failed to get response from AI: ${error.message}`);
  }
}

// Extract relevant information from text using AI
export async function extractInfoFromText<T = any>(
  text: string,
  instructions: string,
  model: string = 'gpt-4o',
  context: { agentId?: string; planId?: string } = {}
): Promise<T> {
  try {
    // Call the abstracted LLM service
    return await llm.extractInfo<T>(
      text,
      instructions,
      { model },
      {
        operation: 'extract_info',
        agentId: context.agentId,
        planId: context.planId
      }
    );
  } catch (error: any) {
    throw new Error(`Failed to extract information: ${error.message}`);
  }
}

// Generate embeddings for text to use in similarity searches
export async function generateEmbedding(
  text: string,
  context: { agentId?: string; planId?: string } = {}
): Promise<number[]> {
  try {
    // Call the abstracted LLM service
    const response = await llm.generateEmbedding(
      text,
      { model: 'text-embedding-3-small' },
      {
        operation: 'embedding',
        agentId: context.agentId,
        planId: context.planId
      }
    );
    
    return response.embedding;
  } catch (error: any) {
    throw new Error(`Failed to generate embedding: ${error.message}`);
  }
}