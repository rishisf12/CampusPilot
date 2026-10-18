/** OppFeed API client for admin module.
 *
 * Re-exports the shared oppfeedApi from @/api and the OppFeed types
 * from shared/types so admin components can import everything from one place.
 */
export { oppfeedApi } from '@/api';

export type {
  OpportunityCard,
  OpportunityDetail,
  OpportunityListItem,
  OpportunityDetailAdmin,
  PaginatedOpportunities,
  FeedFilters,
  OpportunityFilterParams,
  OpportunityUpdateRequest,
  BulkActionRequest,
  StateTransitionRequest,
  RunListItem,
  RunResponse,
  RunStepResponse,
  RunCreateRequest,
  AgentSettingsResponse,
  AgentSettingsUpdateRequest,
  SourceRuleResponse,
  SourceRuleCreateRequest,
  SourceRuleUpdateRequest,
  SearchQueryResponse,
  SearchQueryCreateRequest,
  SearchQueryUpdateRequest,
  ProviderHealth,
  LLMStatusResponse,
  LLMTestRequest,
  LLMTestResponse,
  OppFeedFeedbackResponse,
  OppFeedFeedbackCreateRequest,
} from '@/shared/types/api';
