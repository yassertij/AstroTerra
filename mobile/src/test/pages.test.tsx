import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => false } }));
vi.mock("@capacitor/camera", () => ({ Camera: {}, CameraResultType: {}, CameraSource: {} }));
vi.mock("@capacitor/geolocation", () => ({ Geolocation: { getCurrentPosition: vi.fn(), requestPermissions: vi.fn() } }));
vi.mock("../components/EarthMap", () => ({ EarthMap: () => <div>map</div>, tileBounds: () => null }));

import { ComparePage } from "../components/ComparePage";
import { MoonPage } from "../components/MoonPage";
import { Button } from "../components/ui/Button";
import App from "../App";
import { RESULT } from "./fixtures";

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockImplementation((url: string) => Promise.resolve(new Response(JSON.stringify(
    url.endsWith("/health") ? { status: "ok", synthetic_data: false, disclaimer: "", core_version: "0.1.0" }
      : { synthetic_data: false, mars_megdr: [], earth_srtm: [{ tile: "N38W111", num_file: true }] }), { status: 200 })));
  vi.stubGlobal("fetch", fetchMock);
  localStorage.clear();
  window.location.hash = "";
});

describe("ComparePage", () => {
  it("compares the Mars target with real candidate values, units and unavailable fields", () => {
    render(<ComparePage result={RESULT} selected={[]} setSelected={() => {}} go={() => {}} />);
    // candidate value = target - difference: 3375 - 2607.7 = 767.3 m
    expect(screen.getAllByText("767.3 m").length).toBeGreaterThan(0);
    expect(screen.getAllByText("3375.0 m").length).toBeGreaterThan(0);
    expect(screen.getByText(/Temperature, climate, geology/)).toBeTruthy();
    expect(screen.getAllByText(/Unavailable — no lunar data/).length).toBe(2);
    expect(screen.queryByText(/%\s*similar/i)).toBeNull();
  });
  it("asks for an analysis when there is none", () => {
    const go = vi.fn();
    render(<ComparePage result={null} selected={[]} setSelected={() => {}} go={go} />);
    fireEvent.click(screen.getByText("Run an analysis"));
    expect(go).toHaveBeenCalledWith("analysis");
  });
});

describe("MoonPage", () => {
  it("states that no lunar data is available and shows no measurements", () => {
    render(<MoonPage datasets={null} go={() => {}} />);
    expect(screen.getByRole("heading", { name: /not available yet/i })).toBeTruthy();
    expect(screen.getByText(/does not suggest|Nothing here suggests/)).toBeTruthy();
  });
});

describe("Button", () => {
  it("loading disables and marks busy; disabled blocks clicks", () => {
    const click = vi.fn();
    const { rerender } = render(<Button loading onClick={click}>Go</Button>);
    const b = screen.getByRole("button", { name: "Go" });
    expect(b.getAttribute("aria-busy")).toBe("true");
    expect((b as HTMLButtonElement).disabled).toBe(true);
    rerender(<Button variant="aurora" size="lg" onClick={click}>Go</Button>);
    expect(b.className).toContain("btn-aurora");
    expect(b.className).toContain("btn-lg");
    fireEvent.click(b);
    expect(click).toHaveBeenCalledTimes(1);
  });
});

describe("App navigation", () => {
  it("hash links switch pages and mark the active link", async () => {
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Earth is our testing ground." })).toBeTruthy();
    await act(async () => {
      window.location.hash = "#/moon";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(screen.getByRole("heading", { name: /Lunar analogues are not available yet/ })).toBeTruthy();
    const active = document.querySelector('.navlink[aria-current="page"]');
    expect(active?.textContent).toContain("Moon");
    await act(async () => { fireEvent.click(screen.getByText("Explore Mars analogues")); window.dispatchEvent(new HashChangeEvent("hashchange")); });
    expect(window.location.hash).toBe("#/mars");
  });
  it("hero actions are functional", async () => {
    render(<App />);
    await act(async () => { fireEvent.click(await screen.findByText("Compare planetary environments")); window.dispatchEvent(new HashChangeEvent("hashchange")); });
    expect(window.location.hash).toBe("#/compare");
    expect(screen.getByRole("heading", { name: "Compare planetary environments" })).toBeTruthy();
  });
});
