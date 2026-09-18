export type UserRole =
  | "platform_admin"
  | "tenant_admin"
  | "researcher"
  | "trader"
  | "auditor";

export type ProviderType =
  | "openai"
  | "anthropic"
  | "deepseek"
  | "openai_compatible"
  | "ollama"
  | "vllm";

export type ModelConfiguration = {
  id: string;
  name: string;
  providerType: ProviderType;
  baseUrl: string;
  modelId: string;
  secretStatus: "configured" | "managed" | "missing";
  availability: "available" | "planned";
  enabled: boolean;
  healthStatus: "healthy" | "untested" | "unhealthy";
  allowedEnvironments: string[];
};

export type CreateModelConfiguration = Omit<
  ModelConfiguration,
  "id" | "secretStatus" | "availability" | "healthStatus"
> & {
  apiKey: string;
};

const API_ROOT = "/api/v1/tenant/model-configurations";

export async function fetchModelConfigurations(
  accessToken: string,
): Promise<ModelConfiguration[]> {
  const response = await fetch(API_ROOT, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) {
    throw new Error("加载模型服务失败");
  }
  return response.json() as Promise<ModelConfiguration[]>;
}

export async function createModelConfiguration(
  accessToken: string,
  configuration: CreateModelConfiguration,
): Promise<ModelConfiguration> {
  const response = await fetch(API_ROOT, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(configuration),
  });
  if (!response.ok) {
    throw new Error("保存模型服务失败");
  }
  return response.json() as Promise<ModelConfiguration>;
}
