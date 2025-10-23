/**
 * Internal models for Business-Use SDK.
 */

import { z } from 'zod';

/**
 * Node/Event type literal
 */
export const NodeTypeSchema = z.enum(['act', 'assert', 'generic', 'trigger', 'hook']);
export type NodeType = z.infer<typeof NodeTypeSchema>;

/**
 * Expression engine type literal
 */
export const ExprEngineSchema = z.enum(['python', 'js', 'cel']);
export type ExprEngine = z.infer<typeof ExprEngineSchema>;

/**
 * Type definitions for validator and filter context
 */

/**
 * Upstream dependency event data
 */
export interface DepData {
  /** Flow identifier */
  flow: string;
  /** Node/event identifier */
  id: string;
  /** Event data payload */
  data: Record<string, any>;
}

/**
 * Context passed to filter and validator functions
 */
export interface Ctx {
  /** List of upstream dependency event data */
  deps: DepData[];
  /** Convenience field - populated with deps[0].data when there's exactly one dependency */
  data?: Record<string, any>;
}

/**
 * Expression that can be executed on the backend
 */
export const ExprSchema = z.object({
  engine: ExprEngineSchema,
  script: z.string(),
});
export type Expr = z.infer<typeof ExprSchema>;

/**
 * Condition for node execution
 */
export const NodeConditionSchema = z.object({
  timeout_ms: z.number().optional(),
});
export type NodeCondition = z.infer<typeof NodeConditionSchema>;

/**
 * Event item for batch submission to backend API
 */
export const EventBatchItemSchema = z.object({
  flow: z.string(),
  id: z.string(),
  run_id: z.string(),
  type: NodeTypeSchema,
  data: z.record(z.any()),
  ts: z.number(), // Nanoseconds timestamp
  description: z.string().optional(),
  dep_ids: z.array(z.string()).optional(),
  filter: ExprSchema.optional(),
  validator: ExprSchema.optional(),
  conditions: z.array(NodeConditionSchema).optional(),
  additional_meta: z.record(z.any()).optional(),
});
export type EventBatchItem = z.infer<typeof EventBatchItemSchema>;

/**
 * Internal representation of an event before batching
 */
export interface QueuedEvent {
  flow: string;
  id: string;
  run_id: string | (() => string);
  type: NodeType;
  data: Record<string, any>;
  description?: string;
  dep_ids?: string[] | (() => string[]);
  filter?: boolean | ((_data: Record<string, any>, _ctx: Ctx) => boolean);
  validator?: (_data: Record<string, any>, _ctx: Ctx) => boolean;
  conditions?: NodeCondition[] | (() => NodeCondition[]);
  additional_meta?: Record<string, any>;
}
